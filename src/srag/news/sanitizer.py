"""Treats every news result as untrusted: domain, date, size and prompt-injection checks."""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

from srag.config import NEWS_ALLOWED_DOMAINS, NEWS_SNIPPET_MAX_CHARS, NEWS_TITLE_MAX_CHARS
from srag.news.models import NewsItem

FUTURE_TOLERANCE_DAYS = 1
ELLIPSIS = "…"

DISCARDED_MALFORMED = "malformed"
DISCARDED_DOMAIN = "domain_not_allowed"
DISCARDED_NO_DATE = "missing_date"
DISCARDED_OUT_OF_RANGE = "date_out_of_range"
DISCARDED_DUPLICATE = "duplicate_url"
DISCARDED_INJECTION_IN_TITLE = "injection_in_title"
DISCARDED_EMPTY = "empty_after_sanitization"

_HTML_TAG = re.compile(r"<[^>]*>")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_UNSAFE_URL_CHARS = re.compile(r"[\s<>\"']")

# Phrases that try to give orders to the model (Portuguese and English).
_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(ignore|ignorar|ignorem|desconsidere|desconsiderar|esqueça|esqueca)\b"
        r"[^.]{0,40}\b(instru|regras|prompt|anterior|acima)",
        r"\b(ignore|disregard|forget|override)\b[^.]{0,40}\b(instructions?|rules|prompt|previous|above)",
        r"\b(you are now|você agora é|voce agora e|você é agora|a partir de agora você)\b",
        r"\b(act as|aja como|finja ser|pretend to be)\b",
        r"\b(system prompt|prompt do sistema|developer message)\b",
        r"\b(new instructions?|novas? instruç(ão|ões)|novas? instrucoes?)\b",
        r"^\s*(system|assistant|user|sistema|assistente)\s*:",
        r"\b(do not|don't|não|nao)\s+(follow|obey|siga|obedeça)\b",
        r"\b(responda|answer|reply|respond)\s+(only|apenas|somente)\b",
        r"\b(reveal|revele|mostre|print)\b[^.]{0,30}"
        r"\b(prompt|instruções|instructions|api key|chave)\b",
    )
)


class _RejectedError(Exception):
    """Internal signal: the news result must be discarded for the given reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SanitizationResult:
    items: tuple[NewsItem, ...]
    discarded: dict[str, int]
    sentences_removed: int


def strip_injection(text: str) -> tuple[str, int]:
    """Drop sentences that look like instructions to the model; return the text and the count."""
    sentences = [part for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    kept = [s for s in sentences if not any(p.search(s) for p in _INJECTION_PATTERNS)]
    return " ".join(kept), len(sentences) - len(kept)


def clean_text(text: str, max_chars: int) -> str:
    """Remove markup and control characters, collapse spaces and truncate."""
    text = _SPACES.sub(" ", _CONTROL_CHARS.sub("", _HTML_TAG.sub(" ", text))).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(ELLIPSIS)].rstrip() + ELLIPSIS


def parse_published_date(value: object) -> date | None:
    """Parse the provider's publication date (RFC 2822 or ISO 8601); None if unreadable."""
    if not isinstance(value, str):
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def is_allowed_domain(host: str, allowed_domains: Iterable[str]) -> bool:
    """True when host is an allowed domain or a subdomain of one (never a look-alike)."""
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def sanitize_results(
    raw_results: Iterable[dict[str, Any]],
    today: date,
    news_days: int,
    max_results: int,
    allowed_domains: Iterable[str] = NEWS_ALLOWED_DOMAINS,
) -> SanitizationResult:
    """Keep only trustworthy results and report what was discarded and why."""
    allowed = tuple(allowed_domains)
    items: list[NewsItem] = []
    discarded: Counter[str] = Counter()
    sentences_removed = 0
    seen_urls: set[str] = set()
    for raw in raw_results:
        try:
            item, removed = _build_item(raw, today, news_days, allowed)
            if item.url in seen_urls:
                raise _RejectedError(DISCARDED_DUPLICATE)
        except _RejectedError as rejection:
            discarded[rejection.reason] += 1
            continue
        seen_urls.add(item.url)
        items.append(item)
        sentences_removed += removed
    return SanitizationResult(tuple(items[:max_results]), dict(discarded), sentences_removed)


def _build_item(
    raw: dict[str, Any], today: date, news_days: int, allowed: tuple[str, ...]
) -> tuple[NewsItem, int]:
    url, title, content = raw.get("url"), raw.get("title"), raw.get("content")
    if not all(isinstance(value, str) and value for value in (url, title, content)):
        raise _RejectedError(DISCARDED_MALFORMED)
    host = _allowed_host(url, allowed)
    published_at = _recent_date(raw.get("published_date"), today, news_days)
    clean_title, title_removed = strip_injection(clean_text(title, NEWS_TITLE_MAX_CHARS))
    if title_removed:
        raise _RejectedError(DISCARDED_INJECTION_IN_TITLE)
    safe_content, removed = strip_injection(_HTML_TAG.sub(" ", content))
    snippet = clean_text(safe_content, NEWS_SNIPPET_MAX_CHARS)
    if not clean_title or not snippet:
        raise _RejectedError(DISCARDED_EMPTY)
    source = host.removeprefix("www.")
    return NewsItem(clean_title, url, source, published_at, snippet), removed


def _allowed_host(url: str, allowed: tuple[str, ...]) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or _UNSAFE_URL_CHARS.search(url) or not host:
        raise _RejectedError(DISCARDED_MALFORMED)
    if not is_allowed_domain(host, allowed):
        raise _RejectedError(DISCARDED_DOMAIN)
    return host


def _recent_date(value: object, today: date, news_days: int) -> date:
    published_at = parse_published_date(value)
    if published_at is None:
        raise _RejectedError(DISCARDED_NO_DATE)
    oldest = today - timedelta(days=news_days)
    newest = today + timedelta(days=FUTURE_TOLERANCE_DAYS)
    if not oldest <= published_at <= newest:
        raise _RejectedError(DISCARDED_OUT_OF_RANGE)
    return published_at
