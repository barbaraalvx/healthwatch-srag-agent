"""News search for one scope: builds the query, calls the provider, sanitizes the results."""

from dataclasses import dataclass
from datetime import date

from srag.config import NEWS_COUNTRY_NAME, NEWS_QUERY_MAX_CHARS, UF_NAMES, Settings
from srag.news.client import NewsSearcher
from srag.news.models import NewsItem
from srag.news.relevance import filter_relevant
from srag.news.sanitizer import sanitize_results

DISCARDED_NOT_RELEVANT = "not_relevant"


@dataclass(frozen=True)
class NewsSearchResult:
    query: str
    items: tuple[NewsItem, ...]
    discarded: dict[str, int]
    sentences_removed: int


def build_query(query: str, uf: str | None) -> str:
    """Append the scope (state name or Brazil) so results are about the selected area."""
    if uf is not None and uf not in UF_NAMES:
        raise ValueError(f"Invalid UF: {uf}")
    scope = UF_NAMES[uf] if uf else NEWS_COUNTRY_NAME
    base = " ".join(query.split())[:NEWS_QUERY_MAX_CHARS]
    if not base:
        raise ValueError("News query must not be empty")
    return f"{base} {scope}"


def search_news(
    query: str, uf: str | None, searcher: NewsSearcher, settings: Settings, today: date
) -> NewsSearchResult:
    """Return trustworthy recent news; an empty list means nothing trustworthy was found."""
    full_query = build_query(query, uf)
    sanitized = sanitize_results(searcher.search(full_query), today, settings.news_days)
    relevant = filter_relevant(sanitized.items, uf)
    discarded = dict(sanitized.discarded)
    if len(relevant) < len(sanitized.items):
        discarded[DISCARDED_NOT_RELEVANT] = len(sanitized.items) - len(relevant)
    return NewsSearchResult(
        full_query, relevant[: settings.news_max_items], discarded, sanitized.sentences_removed
    )
