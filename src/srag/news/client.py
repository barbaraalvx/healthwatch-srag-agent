"""Thin wrapper over Tavily: one cheap news search restricted to allowlisted domains."""

from typing import Any, Protocol

import requests
from tavily import TavilyClient
from tavily.errors import (
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    UsageLimitExceededError,
)
from tavily.errors import TimeoutError as TavilyTimeoutError

from srag.config import NEWS_ALLOWED_DOMAINS, Settings

# "basic" depth costs 1 credit per search ("advanced" costs more).
SEARCH_DEPTH = "basic"
TOPIC = "news"

_TAVILY_ERRORS = (
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    UsageLimitExceededError,
    TavilyTimeoutError,
    requests.RequestException,
)


class NewsSearchError(RuntimeError):
    """Raised when the news provider cannot be reached or refuses the request."""


class NewsSearcher(Protocol):
    def search(self, query: str) -> list[dict[str, Any]]: ...


class TavilyNewsSearcher:
    """Searches recent news on allowlisted domains. Each call spends Tavily credits."""

    def __init__(self, settings: Settings) -> None:
        api_key = settings.tavily_api_key.get_secret_value()
        if not api_key:
            raise NewsSearchError("TAVILY_API_KEY is not set")
        self._client = TavilyClient(api_key=api_key)
        self._settings = settings

    def search(self, query: str) -> list[dict[str, Any]]:
        try:
            response = self._client.search(
                query=query,
                search_depth=SEARCH_DEPTH,
                topic=TOPIC,
                days=self._settings.news_days,
                max_results=self._settings.news_max_results,
                include_domains=list(NEWS_ALLOWED_DOMAINS),
                include_answer=False,
                include_raw_content=False,
                include_images=False,
                timeout=self._settings.news_timeout_seconds,
            )
        except _TAVILY_ERRORS as error:
            raise NewsSearchError(f"News search failed ({type(error).__name__})") from error
        return response.get("results", [])
