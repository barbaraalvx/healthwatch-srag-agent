import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END

from srag.agent.graph import (
    FALLBACK,
    ORCHESTRATOR,
    OUTPUT_GUARDRAIL,
    REQUIRED_TOOLS_CHECK,
    TOOLS,
    WRITER,
    route_after_check,
    route_after_guardrail,
    route_after_orchestrator,
    route_after_tools,
    route_after_writer,
)
from srag.guardrails.output import ValidationResult
from srag.news.models import NewsItem

NEWS = (NewsItem("t", "https://g1.globo.com/x", "g1.globo.com", None, "s"),)
WITH_TOOL_CALL = AIMessage("", tool_calls=[{"name": "get_metrics", "args": {}, "id": "1"}])
WITHOUT_TOOL_CALL = AIMessage("Coleta concluída.")
PASSED = ValidationResult(True, ())
FAILED = ValidationResult(False, ("erro",))


def test_orchestrator_goes_to_tools_only_when_it_asks_for_them():
    assert route_after_orchestrator({"messages": [WITH_TOOL_CALL]}) == TOOLS
    assert route_after_orchestrator({"messages": [WITHOUT_TOOL_CALL]}) == REQUIRED_TOOLS_CHECK


def test_a_stopped_run_skips_straight_to_the_required_tools_check():
    state = {"messages": [WITH_TOOL_CALL], "stop_reason": "max_cost_exceeded"}

    assert route_after_orchestrator(state) == REQUIRED_TOOLS_CHECK
    assert route_after_tools(state, max_searches=2) == REQUIRED_TOOLS_CHECK


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"snapshot": 1, "daily_chart": 1, "news_items": NEWS}, REQUIRED_TOOLS_CHECK),
        ({"snapshot": 1, "daily_chart": 1, "searches_done": 2}, REQUIRED_TOOLS_CHECK),
        ({"snapshot": 1, "daily_chart": 1, "searches_done": 1}, ORCHESTRATOR),
        ({"snapshot": 1, "daily_chart": 1}, ORCHESTRATOR),
        ({"news_items": NEWS}, ORCHESTRATOR),
        ({"snapshot": 1, "news_items": NEWS}, ORCHESTRATOR),
        ({}, ORCHESTRATOR),
    ],
)
def test_after_tools_the_orchestrator_is_asked_again_only_if_something_is_missing(state, expected):
    assert route_after_tools(state, max_searches=2) == expected


def test_after_the_check_the_writer_runs_unless_the_run_was_stopped():
    assert route_after_check({}) == WRITER
    assert route_after_check({"stop_reason": "llm_error"}) == FALLBACK


def test_after_the_writer_the_guardrail_runs_unless_the_run_was_stopped():
    assert route_after_writer({}) == OUTPUT_GUARDRAIL
    assert route_after_writer({"stop_reason": "max_cost_exceeded"}) == FALLBACK


@pytest.mark.parametrize(
    ("validation", "attempts", "expected"),
    [
        (PASSED, 1, END),
        (PASSED, 2, END),
        (FAILED, 1, WRITER),
        (FAILED, 2, FALLBACK),
        (FAILED, 3, FALLBACK),
    ],
)
def test_guardrail_result_decides_between_end_retry_and_fallback(validation, attempts, expected):
    state = {"validation": validation, "writer_attempts": attempts}

    assert route_after_guardrail(state) == expected
