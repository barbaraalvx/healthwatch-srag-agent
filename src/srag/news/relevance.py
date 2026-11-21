"""Keeps only news that is about SRAG / respiratory disease and about the selected area."""

import re
import unicodedata
from collections.abc import Iterable

from srag.config import (
    NEWS_COUNTRY_PATTERNS,
    NEWS_INTERNATIONAL_DOMAINS,
    NEWS_TOPIC_PATTERNS,
    UF_NAMES,
)
from srag.news.models import NewsItem
from srag.news.sanitizer import is_allowed_domain

_TOPIC = re.compile(r"\b(?:" + "|".join(NEWS_TOPIC_PATTERNS) + ")")


def normalize(text: str) -> str:
    """Lower-case text without accents, so 'Síndrome' and 'sindrome' match the same pattern."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def is_relevant(item: NewsItem, uf: str | None) -> bool:
    """True when the item is about the topic and, for international sources, about the area."""
    text = normalize(f"{item.title} {item.snippet}")
    if not _TOPIC.search(text):
        return False
    if not is_allowed_domain(item.source, NEWS_INTERNATIONAL_DOMAINS):
        return True
    return _mentions_area(text, uf)


def filter_relevant(items: Iterable[NewsItem], uf: str | None) -> tuple[NewsItem, ...]:
    """Keep only relevant items, in their original order."""
    return tuple(item for item in items if is_relevant(item, uf))


def _mentions_area(text: str, uf: str | None) -> bool:
    patterns = list(NEWS_COUNTRY_PATTERNS)
    if uf is not None:
        patterns.append(re.escape(normalize(UF_NAMES[uf])))
    return any(re.search(rf"\b{pattern}", text) for pattern in patterns)
