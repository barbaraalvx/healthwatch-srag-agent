"""Typed objects shared by the news modules."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class NewsItem:
    """A news result that passed every sanitization rule. Its text is still untrusted.

    published_at is None when the provider gave no date (the search itself is limited to
    the recent period).
    """

    title: str
    url: str
    source: str
    published_at: date | None
    snippet: str
