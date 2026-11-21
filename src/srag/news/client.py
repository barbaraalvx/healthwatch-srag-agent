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
# "news" topic only returned BBC items in a real test; "general" reaches the official sources
# (Fiocruz, gov.br, Agência Brasil) but returns no publication dates. See D-013.
TOPIC = "general"

# Provider time ranges and the largest number of days each one covers.
_TIME_RANGES = (("day", 1), ("week", 7), ("month", 31))
_LONGEST_TIME_RANGE = "year"

_TAVILY_ERRORS = (
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    UsageLimitExceededError,
    TavilyTimeoutError,
    requests.RequestException,
)


def time_range_for(days: int) -> str:
    """Smallest provider time range that covers the given number of days."""
    for name, limit in _TIME_RANGES:
        if days <= limit:
            return name
    return _LONGEST_TIME_RANGE


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
                time_range=time_range_for(self._settings.news_days),
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
