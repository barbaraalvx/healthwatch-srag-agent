"""The nodes of the agent graph. Each node is audited; LLM calls count against the run limits."""

import time
from collections.abc import Callable
from typing import Any

import anthropic
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from srag.agent.dependencies import AgentDependencies
from srag.agent.fallback import REASON_LLM_ERROR, REASON_VALIDATION_FAILED, fallback_text
from srag.agent.prompt_loader import Prompt
from srag.agent.state import STATUS_COMPLETED, STATUS_FALLBACK, STATUS_STOPPED, AgentState
from srag.agent.tools import (
    GET_CASE_SERIES,
    GET_METRICS,
    TOOL_SPECS,
    AgentTools,
    ToolOutcome,
)
from srag.agent.writer_input import build_writer_input
from srag.audit.events import EventDetails, EventType
from srag.config import MEDICAL_DISCLAIMER
from srag.formatting import scope_name
from srag.guardrails.limits import LimitExceededError, llm_cost_usd
from srag.guardrails.output import (
    OutputContext,
    ValidationResult,
    structural_numbers,
    validate_output,
)
from srag.news.untrusted_block import format_untrusted_block

NodeFunction = Callable[[AgentState], dict[str, Any]]
MS_PER_SECOND = 1000
STOP_MAX_TOKENS = "max_tokens"
TRUNCATED_TEXT_ERROR = (
    "The text was cut off because it reached the token limit; write a much shorter text"
)


class LlmCallError(RuntimeError):
    """Raised when the model provider cannot answer (network, quota, server error)."""


def message_text(message: BaseMessage) -> str:
    """The plain text of a message, ignoring thinking and tool blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


class AgentNodes:
    """Node implementations bound to the run's dependencies and prompts."""

    def __init__(
        self,
        deps: AgentDependencies,
        uf: str | None,
        orchestrator_prompt: Prompt,
        writer_prompt: Prompt,
    ) -> None:
        self._deps = deps
        self._uf = uf
        self._orchestrator_prompt = orchestrator_prompt
        self._writer_prompt = writer_prompt
        self._tools = AgentTools(deps, uf)
        self._orchestrator_llm = deps.llm.bind_tools(TOOL_SPECS)

    def initial_messages(self) -> list[BaseMessage]:
        """System prompt and task for the orchestrator."""
        task = f"Gere os dados do relatório de SRAG para o escopo: {scope_name(self._uf)}."
        return [SystemMessage(self._orchestrator_prompt.text), HumanMessage(task)]

    def audited(self, name: str, node: NodeFunction) -> NodeFunction:
        """Wrap a node so it logs node_start, node_end (with duration) and unexpected errors."""

        def wrapper(state: AgentState) -> dict[str, Any]:
            audit = self._deps.audit
            audit.log_event(EventType.NODE_START, name)
            started = time.monotonic()
            try:
                update = node(state)
            except Exception as error:
                audit.log_event(EventType.ERROR, name, EventDetails(reason=type(error).__name__))
                raise
            audit.log_event(
                EventType.NODE_END, name, EventDetails(duration_ms=_elapsed_ms(started))
            )
            return update

        return wrapper

    def orchestrator(self, state: AgentState) -> dict[str, Any]:
        try:
            response = self._call_llm(
                self._orchestrator_llm,
                state["messages"],
                "orchestrator",
                self._orchestrator_prompt.name,
            )
        except (LimitExceededError, LlmCallError) as stop:
            return self._stop(stop, "orchestrator")
        return {"messages": [response]}

    def tools(self, state: AgentState) -> dict[str, Any]:
        working: AgentState = dict(state)
        tool_messages: list[ToolMessage] = []
        updates: dict[str, Any] = {}
        try:
            self._deps.limits.check_timeout()
        except LimitExceededError as stop:
            return self._stop(stop, "tools")
        for call in state["messages"][-1].tool_calls:
            outcome = self._execute(call["name"], call["args"], working)
            working.update(outcome.updates)
            updates.update(outcome.updates)
            tool_messages.append(
                ToolMessage(content=outcome.text, tool_call_id=call["id"], name=call["name"])
            )
        return {**updates, "messages": tool_messages}

    def required_tools_check(self, state: AgentState) -> dict[str, Any]:
        """Run any required tool the model skipped, deterministically."""
        working: AgentState = dict(state)
        updates: dict[str, Any] = {}
        missing = ((GET_METRICS, "snapshot"), (GET_CASE_SERIES, "daily_chart"))
        for tool_name, key in missing:
            if key not in working:
                outcome = self._execute(tool_name, {}, working, decision="deterministic_fallback")
                working.update(outcome.updates)
                updates.update(outcome.updates)
        return updates

    def writer(self, state: AgentState) -> dict[str, Any]:
        attempts = state.get("writer_attempts", 0)
        try:
            response = self._call_llm(
                self._deps.llm, self._writer_messages(state), "writer", self._writer_prompt.name
            )
        except (LimitExceededError, LlmCallError) as stop:
            return self._stop(stop, "writer")
        return {
            "draft": message_text(response),
            "draft_truncated": response.response_metadata.get("stop_reason") == STOP_MAX_TOKENS,
            "writer_attempts": attempts + 1,
        }

    def output_guardrail(self, state: AgentState) -> dict[str, Any]:
        full_text = f"{state['draft'].rstrip()}\n\n{MEDICAL_DISCLAIMER}\n"
        snapshot = state["snapshot"]
        context = OutputContext(
            metrics=snapshot.metrics,
            news=state.get("news_items", ()),
            reference_date=snapshot.reference_date,
            structural_numbers=structural_numbers(self._deps.settings),
        )
        result = validate_output(full_text, context)
        if state.get("draft_truncated"):
            result = ValidationResult(False, (TRUNCATED_TEXT_ERROR, *result.errors))
        self._deps.audit.log_event(
            EventType.GUARDRAIL,
            "output_guardrail",
            EventDetails(
                decision="pass" if result.passed else "fail",
                reason="; ".join(result.errors) or "all checks passed",
                output_summary={"errors": len(result.errors)},
            ),
        )
        if not result.passed:
            return {"validation": result}
        return {"validation": result, "report_text": full_text, "status": STATUS_COMPLETED}

    def fallback(self, state: AgentState) -> dict[str, Any]:
        reason = state.get("stop_reason") or REASON_VALIDATION_FAILED
        status = STATUS_STOPPED if state.get("stop_reason") else STATUS_FALLBACK
        self._deps.audit.log_event(
            EventType.GUARDRAIL,
            "fallback",
            EventDetails(decision="template_only_report", reason=reason),
        )
        return {"report_text": fallback_text(reason), "status": status}

    def _execute(
        self, name: str, args: dict[str, Any], state: AgentState, decision: str | None = None
    ) -> ToolOutcome:
        started = time.monotonic()
        outcome = self._tools.run(name, args, state)
        audit = self._deps.audit
        audit.log_event(
            EventType.TOOL_CALL,
            name,
            EventDetails(
                inputs=args,
                output_summary=outcome.summary or outcome.text,
                duration_ms=_elapsed_ms(started),
                decision=decision,
            ),
        )
        if outcome.error:
            audit.log_event(EventType.ERROR, name, EventDetails(reason=outcome.error))
        return outcome

    def _call_llm(
        self, llm: Any, messages: list[BaseMessage], node: str, prompt_name: str
    ) -> AIMessage:
        limits, settings = self._deps.limits, self._deps.settings
        limits.count_iteration()
        started = time.monotonic()
        try:
            response = llm.invoke(messages)
        except anthropic.APIError as error:
            raise LlmCallError(f"Model call failed ({type(error).__name__})") from error
        usage = response.usage_metadata or {}
        tokens_in, tokens_out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        cost = llm_cost_usd(tokens_in, tokens_out, settings)
        self._deps.audit.log_event(
            EventType.LLM_CALL,
            node,
            EventDetails(
                model=settings.llm_model,
                prompt_version=prompt_name,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                duration_ms=_elapsed_ms(started),
                output_summary={"tool_calls": [call["name"] for call in response.tool_calls]},
            ),
        )
        limits.add_cost(cost)
        return response

    def _writer_messages(self, state: AgentState) -> list[BaseMessage]:
        news_block = format_untrusted_block(state.get("news_items", ()))
        messages: list[BaseMessage] = [
            SystemMessage(self._writer_prompt.text),
            HumanMessage(build_writer_input(state["snapshot"], news_block)),
        ]
        validation = state.get("validation")
        if validation is not None and not validation.passed:
            feedback = "\n".join(f"- {error}" for error in validation.errors)
            messages += [
                AIMessage(state["draft"]),
                HumanMessage(
                    "Seu texto foi reprovado nas verificações automáticas:\n"
                    f"{feedback}\n"
                    "Reescreva o texto completo, corrigindo esses problemas e usando somente "
                    "os números e as URLs fornecidos."
                ),
            ]
        return messages

    def _stop(self, stop: Exception, node: str) -> dict[str, Any]:
        reason = stop.reason if isinstance(stop, LimitExceededError) else REASON_LLM_ERROR
        self._deps.audit.log_event(
            EventType.GUARDRAIL, node, EventDetails(decision="stop", reason=reason)
        )
        return {"stop_reason": reason}


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * MS_PER_SECOND)
