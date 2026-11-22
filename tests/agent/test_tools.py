import pytest

from srag.agent.tools import (
    GET_CASE_SERIES,
    GET_METRICS,
    SEARCH_NEWS,
    TOOL_SPECS,
    AgentTools,
    merge_news,
)
from srag.news.models import NewsItem
from tests.agent.fakes import FakeChatModel, FakeSearcher, news_result, search_error
from tests.agent.helpers import make_deps


def item(number: int) -> NewsItem:
    return NewsItem(f"t{number}", f"https://g1.globo.com/{number}", "g1.globo.com", None, "s")


@pytest.fixture
def tools(tmp_path, repository, settings):
    searcher = FakeSearcher([[news_result(1)], [news_result(2)], [news_result(3)]])
    deps = make_deps(tmp_path, repository, FakeChatModel(script=[]), searcher, settings)
    return AgentTools(deps, "SP"), searcher


def test_the_three_tools_are_exposed_with_schemas_and_no_free_form_fields():
    names = [spec["name"] for spec in TOOL_SPECS]

    assert names == [GET_METRICS, GET_CASE_SERIES, SEARCH_NEWS]
    properties = {spec["name"]: spec["input_schema"]["properties"] for spec in TOOL_SPECS}
    assert properties[GET_METRICS] == {} and properties[GET_CASE_SERIES] == {}
    assert list(properties[SEARCH_NEWS]) == ["query"]  # no uf: the scope is fixed by the run
    assert all(spec["description"] for spec in TOOL_SPECS)


def test_merge_news_keeps_order_drops_repeated_urls_and_respects_the_limit():
    merged = merge_news((item(1), item(2)), (item(2), item(3), item(4)), limit=3)

    assert [n.url[-1] for n in merged] == ["1", "2", "3"]


def test_get_metrics_returns_a_status_line_and_the_snapshot(tools):
    runner, _ = tools

    outcome = runner.run(GET_METRICS, {}, {})

    assert outcome.text.startswith("Métricas calculadas (5). Data de referência: 15/11/2026")
    assert outcome.updates["snapshot"].uf == "SP"
    assert not any(
        char.isdigit() for char in outcome.text.replace("15/11/2026", "").replace("(5)", "")
    )


def test_repeated_calls_do_not_recompute(tools):
    runner, _ = tools

    metrics = runner.run(GET_METRICS, {}, {"snapshot": object()})
    charts = runner.run(GET_CASE_SERIES, {}, {"daily_chart": object()})

    assert metrics.updates == {} and "já foram calculadas" in metrics.text
    assert charts.updates == {} and "já foram gerados" in charts.text


def test_case_series_tool_writes_both_charts(tools, tmp_path):
    runner, _ = tools

    outcome = runner.run(GET_CASE_SERIES, {}, {})

    assert outcome.updates["daily_chart"].name == "daily_cases.png"
    assert outcome.updates["monthly_chart"].name == "monthly_cases.png"
    assert outcome.updates["daily_chart"].exists()


def test_search_returns_only_counts_never_news_text(tools):
    runner, _ = tools

    outcome = runner.run(SEARCH_NEWS, {"query": "SRAG"}, {})

    assert outcome.text == (
        "Busca concluída: 1 notícias relevantes (1 no total), 0 descartadas. Buscas restantes: 1."
    )
    assert "InfoGripe" not in outcome.text
    assert outcome.updates["searches_done"] == 1


def test_search_is_rejected_after_the_limit_without_calling_the_provider(tools):
    runner, searcher = tools

    outcome = runner.run(SEARCH_NEWS, {"query": "SRAG"}, {"searches_done": 2})

    assert "Limite de buscas atingido" in outcome.text
    assert searcher.queries == []
    assert outcome.updates == {}


@pytest.mark.parametrize(
    "args", [{}, {"query": ""}, {"query": "   "}, {"query": 5}, {"query": None}]
)
def test_search_with_an_invalid_query_is_rejected_without_calling_the_provider(tools, args):
    runner, searcher = tools

    outcome = runner.run(SEARCH_NEWS, args, {})

    assert "Consulta inválida" in outcome.text
    assert searcher.queries == []


def test_a_provider_failure_is_reported_and_counted(tmp_path, repository, settings):
    deps = make_deps(
        tmp_path, repository, FakeChatModel(script=[]), FakeSearcher([search_error()]), settings
    )

    outcome = AgentTools(deps, "SP").run(SEARCH_NEWS, {"query": "SRAG"}, {})

    assert "Prossiga sem notícias" in outcome.text
    assert outcome.updates == {"searches_done": 1}
    assert "failed" in outcome.error


def test_a_second_search_adds_to_the_news_already_found(tools):
    runner, _ = tools
    first = runner.run(SEARCH_NEWS, {"query": "SRAG"}, {})

    second = runner.run(SEARCH_NEWS, {"query": "gripe"}, {**first.updates})

    assert [n.url[-1] for n in second.updates["news_items"]] == ["1", "2"]
