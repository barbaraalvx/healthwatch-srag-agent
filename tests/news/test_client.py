import pytest
import requests
from tavily.errors import UsageLimitExceededError

from srag.config import NEWS_ALLOWED_DOMAINS, Settings
from srag.news import client
from srag.news.client import NewsSearchError, TavilyNewsSearcher


class FakeTavilyClient:
    last_search_kwargs: dict = {}
    error: Exception | None = None

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, **kwargs) -> dict:
        FakeTavilyClient.last_search_kwargs = kwargs
        if FakeTavilyClient.error:
            raise FakeTavilyClient.error
        return {"results": [{"title": "t"}]}


@pytest.fixture(autouse=True)
def fake_tavily(monkeypatch):
    FakeTavilyClient.last_search_kwargs = {}
    FakeTavilyClient.error = None
    monkeypatch.setattr(client, "TavilyClient", FakeTavilyClient)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, tavily_api_key="fake-key", news_max_results=4, news_days=15)


def test_search_asks_for_the_cheapest_restricted_news_search(settings):
    results = TavilyNewsSearcher(settings).search("SRAG Brasil")

    assert results == [{"title": "t"}]
    assert FakeTavilyClient.last_search_kwargs == {
        "query": "SRAG Brasil",
        "search_depth": "basic",
        "topic": "news",
        "days": 15,
        "max_results": 4,
        "include_domains": list(NEWS_ALLOWED_DOMAINS),
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "timeout": settings.news_timeout_seconds,
    }


def test_missing_api_key_fails_before_any_request():
    with pytest.raises(NewsSearchError, match="TAVILY_API_KEY"):
        TavilyNewsSearcher(Settings(_env_file=None))


@pytest.mark.parametrize(
    "error", [UsageLimitExceededError("limit"), requests.ConnectionError("offline")]
)
def test_provider_errors_become_news_search_errors_without_the_message(settings, error):
    FakeTavilyClient.error = error

    with pytest.raises(NewsSearchError) as raised:
        TavilyNewsSearcher(settings).search("SRAG")

    assert "fake-key" not in str(raised.value)
    assert raised.value.__cause__ is error
