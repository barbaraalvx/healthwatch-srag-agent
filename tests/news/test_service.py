from datetime import date

import pytest

from srag.config import NEWS_QUERY_MAX_CHARS, Settings
from srag.news.service import build_query, search_news

TODAY = date(2026, 11, 21)


class FakeSearcher:
    def __init__(self, results: list[dict]) -> None:
        self.results = results
        self.queries: list[str] = []

    def search(self, query: str) -> list[dict]:
        self.queries.append(query)
        return self.results


def valid_result(number: int = 1) -> dict:
    return {
        "title": f"Notícia {number} sobre SRAG",
        "url": f"https://g1.globo.com/saude/{number}",
        "content": "Casos de SRAG aumentaram.",
        "published_date": "2026-11-20",
    }


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, news_max_results=2)


def test_query_for_brazil_ends_with_the_country():
    assert build_query("casos de SRAG", None) == "casos de SRAG Brasil"


def test_query_for_a_state_ends_with_the_state_name():
    assert build_query("casos de SRAG", "SP") == "casos de SRAG São Paulo"


def test_query_spaces_are_collapsed_and_length_is_capped():
    assert build_query("  casos   de\nSRAG ", None) == "casos de SRAG Brasil"
    assert build_query("x" * 1000, None) == "x" * NEWS_QUERY_MAX_CHARS + " Brasil"


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query_is_rejected(query):
    with pytest.raises(ValueError):
        build_query(query, None)


def test_unknown_uf_is_rejected():
    with pytest.raises(ValueError):
        build_query("SRAG", "XX")


def test_search_sends_the_scoped_query_and_returns_sanitized_items(settings):
    searcher = FakeSearcher([valid_result(1)])

    result = search_news("SRAG", "RJ", searcher, settings, TODAY)

    assert searcher.queries == ["SRAG Rio de Janeiro"]
    assert result.query == "SRAG Rio de Janeiro"
    assert [item.url for item in result.items] == ["https://g1.globo.com/saude/1"]


def test_search_reports_what_was_discarded(settings):
    bad = valid_result(2) | {"url": "https://evil.example.com/x"}

    result = search_news("SRAG", None, FakeSearcher([valid_result(1), bad]), settings, TODAY)

    assert len(result.items) == 1
    assert result.discarded == {"domain_not_allowed": 1}


def test_search_returns_an_empty_tuple_when_nothing_is_trustworthy(settings):
    bad = valid_result() | {"url": "https://evil.example.com/x"}

    result = search_news("SRAG", None, FakeSearcher([bad]), settings, TODAY)

    assert result.items == ()


def test_search_limits_the_number_of_items(settings):
    results = [valid_result(number) for number in range(5)]

    result = search_news("SRAG", None, FakeSearcher(results), settings, TODAY)

    assert len(result.items) == settings.news_max_results


def test_search_discards_news_that_is_not_about_the_topic(settings):
    off_topic = valid_result(2) | {"title": "Futebol: resultado da rodada", "content": "Placar."}

    result = search_news("SRAG", None, FakeSearcher([valid_result(1), off_topic]), settings, TODAY)

    assert len(result.items) == 1
    assert result.discarded == {"not_relevant": 1}
