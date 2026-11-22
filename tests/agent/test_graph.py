import json
from pathlib import Path
from unittest.mock import Mock

import anthropic
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from srag.agent.fallback import fallback_text
from srag.agent.graph import run_agent
from srag.config import MEDICAL_DISCLAIMER, Settings
from srag.guardrails.input import InvalidRequestError
from srag.metrics.snapshot import compute_metrics
from tests.agent.fakes import (
    FakeChatModel,
    FakeSearcher,
    done_message,
    news_result,
    search_error,
    text_message,
    tool_calls_message,
)
from tests.agent.helpers import invalid_report_text, make_deps, valid_report_text

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
NEWS_URL = "https://agencia.fiocruz.br/infogripe-1"
ALL_TOOLS = tool_calls_message(
    ("get_metrics", {}), ("get_case_series", {}), ("search_news", {"query": "SRAG casos"})
)


def run(tmp_path, repository, settings, script, batches=(), uf="SP", clock=None):
    llm = FakeChatModel(script=list(script))
    searcher = FakeSearcher(list(batches))
    deps = make_deps(tmp_path, repository, llm, searcher, settings, clock)
    return run_agent(deps, uf), deps, llm, searcher


def audit_events(deps) -> list[dict]:
    lines = deps.audit.audit_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def event_names(deps, event_type: str) -> list[str]:
    return [e["node"] for e in audit_events(deps) if e["event_type"] == event_type]


def guardrail_events(deps, node: str) -> list[dict]:
    return [e for e in audit_events(deps) if e["event_type"] == "guardrail" and e["node"] == node]


def message_texts(messages) -> str:
    return "\n".join(str(message.content) for message in messages)


# --- the normal path ---------------------------------------------------------------------


def test_happy_path_collects_data_writes_and_passes_the_guardrail(
    tmp_path, repository, settings, snapshot
):
    script = [ALL_TOOLS, text_message(valid_report_text(snapshot, NEWS_URL))]

    result, deps, llm, searcher = run(tmp_path, repository, settings, script, [[news_result(1)]])

    assert result.status == "completed"
    assert result.stop_reason is None
    assert result.validation_errors == ()
    assert result.writer_attempts == 1
    assert result.snapshot.uf == "SP"
    assert [item.url for item in result.news_items] == [NEWS_URL]
    assert result.report_text.rstrip().endswith(MEDICAL_DISCLAIMER)
    assert searcher.queries == ["SRAG casos São Paulo"]
    for chart in (result.daily_chart, result.monthly_chart):
        assert chart.read_bytes().startswith(PNG_SIGNATURE)


def test_when_everything_is_collected_the_orchestrator_is_not_called_a_second_time(
    tmp_path, repository, settings, snapshot
):
    script = [ALL_TOOLS, text_message(valid_report_text(snapshot, NEWS_URL))]

    _, _, llm, _ = run(tmp_path, repository, settings, script, [[news_result(1)]])

    assert len(llm.calls) == 2  # orchestrator once, writer once


def test_models_receive_the_prompts_and_the_scope(tmp_path, repository, settings, snapshot):
    script = [ALL_TOOLS, text_message(valid_report_text(snapshot, NEWS_URL))]

    _, _, llm, _ = run(tmp_path, repository, settings, script, [[news_result(1)]])

    orchestrator_call, writer_call = llm.calls
    assert isinstance(orchestrator_call[0], SystemMessage)
    assert "coordena a coleta" in orchestrator_call[0].content
    assert "São Paulo (SP)" in orchestrator_call[1].content
    assert "escreve a análise" in writer_call[0].content
    writer_input = writer_call[1].content
    assert "São Paulo (SP)" in writer_input
    assert "<untrusted_news>" in writer_input and NEWS_URL in writer_input


def test_audit_trail_records_nodes_tools_llm_calls_and_the_guardrail(
    tmp_path, repository, settings, snapshot
):
    script = [ALL_TOOLS, text_message(valid_report_text(snapshot, NEWS_URL))]

    _, deps, _, _ = run(tmp_path, repository, settings, script, [[news_result(1)]])

    events = audit_events(deps)
    assert event_names(deps, "tool_call") == ["get_metrics", "get_case_series", "search_news"]
    assert event_names(deps, "llm_call") == ["orchestrator", "writer"]
    assert event_names(deps, "guardrail") == ["output_guardrail"]
    assert [e["node"] for e in events if e["event_type"] == "node_end"] == [
        "orchestrator",
        "tools",
        "required_tools_check",
        "writer",
        "output_guardrail",
    ]
    llm_events = [e for e in events if e["event_type"] == "llm_call"]
    assert all(e["model"] == "claude-haiku-5-5" and e["cost_usd"] > 0 for e in llm_events)
    assert llm_events[1]["prompt_version"] == "writer_v1"
    search_event = next(e for e in events if e["node"] == "search_news")
    assert search_event["output_summary"]["kept"] == 1
    assert {e["run_id"] for e in events} == {deps.audit.run_id}


def test_the_model_cannot_change_the_scope_and_unknown_tools_are_rejected(
    tmp_path, repository, settings, snapshot
):
    greedy = tool_calls_message(
        ("delete_everything", {}),
        ("get_metrics", {"uf": "AC"}),
        ("get_case_series", {"uf": "AC"}),
        ("search_news", {"query": "SRAG", "uf": "AC"}),
    )
    script = [greedy, text_message(valid_report_text(snapshot, NEWS_URL))]

    result, deps, _, searcher = run(tmp_path, repository, settings, script, [[news_result(1)]])

    assert result.status == "completed"
    assert result.snapshot.uf == "SP"
    assert searcher.queries == ["SRAG São Paulo"]
    rejected = next(e for e in audit_events(deps) if e["node"] == "delete_everything")
    assert rejected["output_summary"] == {"rejected": "unknown tool"}


def test_whole_country_scope(tmp_path, repository, settings):
    brazil = compute_metrics(repository, None, settings)
    script = [ALL_TOOLS, done_message(), text_message(valid_report_text(brazil, None))]

    result, _, llm, searcher = run(tmp_path, repository, settings, script, [[]], uf=None)

    assert result.status == "completed"
    assert result.snapshot.uf is None
    assert searcher.queries == ["SRAG casos Brasil"]
    assert "Brasil" in llm.calls[0][1].content


# --- news --------------------------------------------------------------------------------


def test_the_model_that_calls_tools_never_sees_news_text(tmp_path, repository, settings, snapshot):
    first = tool_calls_message(("search_news", {"query": "SRAG casos"}))
    second = tool_calls_message(("get_metrics", {}), ("get_case_series", {}))
    script = [first, second, text_message(valid_report_text(snapshot, NEWS_URL))]

    _, _, llm, _ = run(tmp_path, repository, settings, script, [[news_result(1)]])

    second_orchestrator_call = llm.calls[1]
    tool_message = next(m for m in second_orchestrator_call if isinstance(m, ToolMessage))
    assert "Busca concluída: 1 notícias relevantes" in tool_message.content
    assert "InfoGripe" not in message_texts(second_orchestrator_call)
    assert NEWS_URL not in message_texts(second_orchestrator_call)


def test_the_model_can_refine_the_query_once_when_nothing_relevant_is_found(
    tmp_path, repository, settings, snapshot
):
    refine = tool_calls_message(("search_news", {"query": "gripe internações"}))
    script = [
        ALL_TOOLS,
        refine,
        text_message(valid_report_text(snapshot, "https://agencia.fiocruz.br/infogripe-2")),
    ]

    result, _, llm, searcher = run(tmp_path, repository, settings, script, [[], [news_result(2)]])

    assert result.status == "completed"
    assert searcher.queries == ["SRAG casos São Paulo", "gripe internações São Paulo"]
    assert len(llm.calls) == 3


def test_search_stops_at_the_configured_limit_and_the_report_says_there_is_no_news(
    tmp_path, repository, settings, snapshot
):
    refine = tool_calls_message(("search_news", {"query": "outra consulta"}))
    script = [ALL_TOOLS, refine, text_message(valid_report_text(snapshot, None))]

    result, _, llm, searcher = run(tmp_path, repository, settings, script, [[], []])

    assert result.status == "completed"
    assert len(searcher.queries) == settings.news_max_searches == 2
    assert result.news_items == ()
    assert "Nenhuma notícia confiável foi encontrada." in llm.calls[2][1].content


def test_a_failed_search_does_not_stop_the_report(tmp_path, repository, settings, snapshot):
    script = [ALL_TOOLS, done_message(), text_message(valid_report_text(snapshot, None))]

    result, deps, _, _ = run(tmp_path, repository, settings, script, [search_error()])

    assert result.status == "completed"
    assert result.news_items == ()
    assert (
        "failed"
        in next(
            e
            for e in audit_events(deps)
            if e["event_type"] == "error" and e["node"] == "search_news"
        )["reason"]
    )


# --- required tools ----------------------------------------------------------------------


def test_skipped_required_tools_are_run_by_the_code(tmp_path, repository, settings, snapshot):
    script = [done_message(), text_message(valid_report_text(snapshot, None))]

    result, deps, _, searcher = run(tmp_path, repository, settings, script)

    assert result.status == "completed"
    assert searcher.queries == []
    tool_events = [e for e in audit_events(deps) if e["event_type"] == "tool_call"]
    assert [(e["node"], e["decision"]) for e in tool_events] == [
        ("get_metrics", "deterministic_fallback"),
        ("get_case_series", "deterministic_fallback"),
    ]
    assert result.daily_chart.exists() and result.monthly_chart.exists()


# --- output guardrail: retry and fallback ------------------------------------------------


def test_a_rejected_text_is_rewritten_once_with_the_errors_as_feedback(
    tmp_path, repository, settings, snapshot
):
    script = [
        ALL_TOOLS,
        text_message(invalid_report_text()),
        text_message(valid_report_text(snapshot, NEWS_URL)),
    ]

    result, deps, llm, _ = run(tmp_path, repository, settings, script, [[news_result(1)]])

    assert result.status == "completed"
    assert result.writer_attempts == 2
    retry_call = llm.calls[2]
    assert [type(m) for m in retry_call] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert retry_call[2].content == invalid_report_text()
    assert "'4.321'" in retry_call[3].content
    decisions = [e["decision"] for e in guardrail_events(deps, "output_guardrail")]
    assert decisions == ["fail", "pass"]


def test_a_text_cut_off_by_the_token_limit_is_rejected_even_if_it_looks_valid(
    tmp_path, repository, settings, snapshot
):
    good_text = valid_report_text(snapshot, NEWS_URL)
    script = [
        ALL_TOOLS,
        text_message(good_text, tokens_out=4000, stop_reason="max_tokens"),
        text_message(good_text),
    ]

    result, deps, llm, _ = run(tmp_path, repository, settings, script, [[news_result(1)]])

    assert result.status == "completed"
    assert result.writer_attempts == 2
    assert "cut off" in llm.calls[2][3].content
    reasons = [e["reason"] for e in guardrail_events(deps, "output_guardrail")]
    assert "token limit" in reasons[0] and reasons[1] == "all checks passed"


def test_two_rejected_texts_produce_a_template_only_report(
    tmp_path, repository, settings, snapshot
):
    script = [ALL_TOOLS, text_message(invalid_report_text()), text_message(invalid_report_text())]

    result, deps, llm, _ = run(tmp_path, repository, settings, script, [[news_result(1)]])

    assert result.status == "fallback"
    assert result.report_text == fallback_text("validation_failed")
    assert result.validation_errors
    assert result.writer_attempts == 2
    assert len(llm.calls) == 3  # never a third writer call
    assert result.daily_chart.exists() and result.snapshot is not None
    assert [e["decision"] for e in guardrail_events(deps, "fallback")] == ["template_only_report"]


# --- limits and failures -----------------------------------------------------------------


def test_cost_limit_stops_the_run_and_still_returns_metrics_and_charts(
    tmp_path, repository, settings, snapshot
):
    cheap = Settings(_env_file=None, max_cost_usd_per_run=0.00001)

    result, deps, llm, _ = run(tmp_path, repository, cheap, [ALL_TOOLS])

    assert result.status == "stopped"
    assert result.stop_reason == "max_cost_exceeded"
    assert "limite de custo" in result.report_text
    assert len(llm.calls) == 1
    assert result.snapshot is not None and result.daily_chart.exists()
    assert any(e["event_type"] == "llm_call" for e in audit_events(deps))
    stop = next(e for e in audit_events(deps) if e.get("decision") == "stop")
    assert stop["reason"] == "max_cost_exceeded"


def test_iteration_limit_stops_the_run(tmp_path, repository, snapshot):
    limited = Settings(_env_file=None, agent_max_iterations=1)
    script = [ALL_TOOLS, text_message(valid_report_text(snapshot, NEWS_URL))]

    result, _, llm, _ = run(tmp_path, repository, limited, script, [[news_result(1)]])

    assert result.status == "stopped"
    assert result.stop_reason == "max_iterations_exceeded"
    assert len(llm.calls) == 1


def test_a_model_that_never_finishes_is_stopped_by_the_iteration_limit(tmp_path, repository):
    limited = Settings(_env_file=None, agent_max_iterations=3)
    script = [tool_calls_message(("unknown_tool", {})) for _ in range(5)]

    result, _, llm, _ = run(tmp_path, repository, limited, script)

    assert result.stop_reason == "max_iterations_exceeded"
    assert len(llm.calls) == 3


def test_timeout_stops_the_run(tmp_path, repository, settings):
    times = iter([0.0])

    def clock() -> float:
        return next(times, 1000.0)

    result, _, llm, _ = run(tmp_path, repository, settings, [], clock=clock)

    assert result.status == "stopped"
    assert result.stop_reason == "run_timeout_exceeded"
    assert llm.calls == []


def test_model_provider_failure_produces_a_template_only_report(tmp_path, repository, settings):
    outage = anthropic.APIConnectionError(request=Mock())

    result, deps, _, _ = run(tmp_path, repository, settings, [outage])

    assert result.status == "stopped"
    assert result.stop_reason == "llm_error"
    assert "serviço do modelo" in result.report_text
    assert result.snapshot is not None


def test_invalid_scope_is_rejected_before_anything_runs(tmp_path, repository, settings):
    llm = FakeChatModel(script=[])
    deps = make_deps(tmp_path, repository, llm, FakeSearcher([]), settings)

    with pytest.raises(InvalidRequestError):
        run_agent(deps, "XX")

    assert llm.calls == []
    assert not Path(deps.audit.audit_path).exists()
