"""LangGraph definition of the report agent and the function that runs it.

START -> orchestrator <-> tools -> required_tools_check -> writer -> output_guardrail
         (writer again on the first failure, fallback on the second)  -> END
A run stopped by a limit or a model error skips to the template-only fallback.
"""

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from srag.agent.dependencies import AgentDependencies
from srag.agent.nodes import AgentNodes
from srag.agent.prompt_loader import load_prompt
from srag.agent.state import AgentState
from srag.config import ORCHESTRATOR_PROMPT, WRITER_MAX_ATTEMPTS, WRITER_PROMPT
from srag.guardrails.input import validate_request
from srag.metrics.snapshot import MetricsSnapshot
from srag.news.models import NewsItem

ORCHESTRATOR = "orchestrator"
TOOLS = "tools"
REQUIRED_TOOLS_CHECK = "required_tools_check"
WRITER = "writer"
OUTPUT_GUARDRAIL = "output_guardrail"
FALLBACK = "fallback"

# Each orchestrator turn is two graph steps (orchestrator + tools); the rest is a fixed margin.
STEPS_PER_ITERATION = 2
RECURSION_MARGIN = 12


@dataclass(frozen=True)
class AgentResult:
    status: str
    report_text: str
    snapshot: MetricsSnapshot
    daily_chart: Path
    monthly_chart: Path
    news_items: tuple[NewsItem, ...]
    stop_reason: str | None
    validation_errors: tuple[str, ...]
    writer_attempts: int


def route_after_orchestrator(state: AgentState) -> str:
    if state.get("stop_reason"):
        return REQUIRED_TOOLS_CHECK
    return TOOLS if state["messages"][-1].tool_calls else REQUIRED_TOOLS_CHECK


def route_after_tools(state: AgentState, max_searches: int) -> str:
    """Skip the extra orchestrator turn when everything needed is already collected."""
    if state.get("stop_reason"):
        return REQUIRED_TOOLS_CHECK
    has_core_data = "snapshot" in state and "daily_chart" in state
    search_settled = bool(state.get("news_items")) or state.get("searches_done", 0) >= max_searches
    return REQUIRED_TOOLS_CHECK if has_core_data and search_settled else ORCHESTRATOR


def route_after_check(state: AgentState) -> str:
    return FALLBACK if state.get("stop_reason") else WRITER


def route_after_writer(state: AgentState) -> str:
    return FALLBACK if state.get("stop_reason") else OUTPUT_GUARDRAIL


def route_after_guardrail(state: AgentState) -> str:
    if state["validation"].passed:
        return END
    return WRITER if state["writer_attempts"] < WRITER_MAX_ATTEMPTS else FALLBACK


def build_graph(nodes: AgentNodes, max_searches: int) -> Any:
    """Compile the agent graph."""
    graph = StateGraph(AgentState)
    functions = {
        ORCHESTRATOR: nodes.orchestrator,
        TOOLS: nodes.tools,
        REQUIRED_TOOLS_CHECK: nodes.required_tools_check,
        WRITER: nodes.writer,
        OUTPUT_GUARDRAIL: nodes.output_guardrail,
        FALLBACK: nodes.fallback,
    }
    for name, function in functions.items():
        graph.add_node(name, nodes.audited(name, function))
    graph.add_edge(START, ORCHESTRATOR)
    graph.add_conditional_edges(ORCHESTRATOR, route_after_orchestrator)
    graph.add_conditional_edges(TOOLS, partial(route_after_tools, max_searches=max_searches))
    graph.add_conditional_edges(REQUIRED_TOOLS_CHECK, route_after_check)
    graph.add_conditional_edges(WRITER, route_after_writer)
    graph.add_conditional_edges(OUTPUT_GUARDRAIL, route_after_guardrail)
    graph.add_edge(FALLBACK, END)
    return graph.compile()


def run_agent(deps: AgentDependencies, uf: str | None) -> AgentResult:
    """Validate the request, run the graph and return the final result."""
    request = validate_request(uf)
    nodes = AgentNodes(
        deps, request.uf, load_prompt(ORCHESTRATOR_PROMPT), load_prompt(WRITER_PROMPT)
    )
    graph = build_graph(nodes, deps.settings.news_max_searches)
    recursion_limit = deps.settings.agent_max_iterations * STEPS_PER_ITERATION + RECURSION_MARGIN
    final = graph.invoke(
        {"messages": nodes.initial_messages()}, {"recursion_limit": recursion_limit}
    )
    return _to_result(final)


def _to_result(final: AgentState) -> AgentResult:
    validation = final.get("validation")
    return AgentResult(
        status=final["status"],
        report_text=final["report_text"],
        snapshot=final["snapshot"],
        daily_chart=final["daily_chart"],
        monthly_chart=final["monthly_chart"],
        news_items=final.get("news_items", ()),
        stop_reason=final.get("stop_reason"),
        validation_errors=validation.errors if validation and not validation.passed else (),
        writer_attempts=final.get("writer_attempts", 0),
    )
