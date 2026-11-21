"""Output guardrail: checks the LLM text against computed values and retrieved sources.

Checks: numbers match computed values (or numbers present in the retrieved news), cited URLs
come from the retrieved news, required sections and the medical disclaimer are present, and
no personal data patterns appear. Dates are not verified (documented limitation).
"""

import re
from dataclasses import dataclass
from datetime import date

from srag.config import (
    DAILY_CHART_DAYS,
    MEDICAL_DISCLAIMER,
    MONTHLY_CHART_MONTHS,
    NUMBER_TOLERANCE,
    REQUIRED_REPORT_SECTIONS,
    Settings,
)
from srag.metrics.calculations import MetricResult
from srag.news.models import NewsItem
from srag.text import normalize

PERCENT = 100
FLOAT_EPSILON = 1e-9
TRAILING_URL_PUNCTUATION = ".,;:!?"

_URL = re.compile(r"https?://[^\s)\]>\"']+")
_DATE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b")
_CODE_WITH_DIGITS = re.compile(r"\b[^\W\d_]+-?\d+[^\W_]*\b")  # COVID-19, H1N1
_LIST_MARKER = re.compile(r"(?m)^\s*\d+[.)]\s+")
_CITATION_MARKER = re.compile(r"\[\d+\]")
_NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
_HEADING = re.compile(r"(?m)^#{1,6}\s*(.+?)\s*$")
_PII_PATTERNS = {
    "CPF": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b"),
    "e-mail": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone number": re.compile(r"\(\d{2}\)\s?9?\d{4}-\d{4}|\+55\s?\d{2}\s?9?\d{4}-?\d{4}"),
}


@dataclass(frozen=True)
class OutputContext:
    """What the text is allowed to say: computed metrics and the retrieved news."""

    metrics: tuple[MetricResult, ...]
    news: tuple[NewsItem, ...]
    reference_date: date
    structural_numbers: tuple[int, ...]


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: tuple[str, ...]


def structural_numbers(settings: Settings) -> tuple[int, ...]:
    """Fixed numbers the text may mention: window sizes, lag, chart spans, minimum sample."""
    return (
        settings.metric_window_days,
        settings.report_lag_days,
        DAILY_CHART_DAYS,
        MONTHLY_CHART_MONTHS,
        settings.min_denominator,
    )


def validate_output(text: str, context: OutputContext) -> ValidationResult:
    """Run every output check; the result lists all problems found."""
    errors = [
        *check_numbers(text, context),
        *check_citations(text, context.news),
        *check_sections(text),
        *check_disclaimer(text),
        *check_personal_data(text),
    ]
    return ValidationResult(passed=not errors, errors=tuple(errors))


def extract_numbers(text: str) -> list[tuple[str, float]]:
    """Numbers written in pt-BR format (1.234,5), ignoring URLs, dates, codes and list markers."""
    for noise in (_URL, _DATE, _LIST_MARKER, _CITATION_MARKER, _CODE_WITH_DIGITS):
        text = noise.sub(" ", text)
    return [(token, _parse_number(token)) for token in _NUMBER.findall(text)]


def _parse_number(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def check_numbers(text: str, context: OutputContext) -> list[str]:
    """Every number must match a computed value (within the tolerance) or a number in the news."""
    computed = _computed_numbers(context)
    from_news = _news_numbers(context.news)
    return [
        f"Number '{token}' does not match any computed value or retrieved source"
        for token, value in extract_numbers(text)
        if not _is_allowed(value, computed, from_news)
    ]


def _computed_numbers(context: OutputContext) -> set[float]:
    allowed = {float(number) for number in context.structural_numbers}
    allowed |= {float(context.reference_date.year), float(context.reference_date.year - 1)}
    for metric in context.metrics:
        allowed |= {float(metric.numerator), float(metric.denominator)}
        allowed.add(round(metric.completeness * PERCENT, 4))
        if metric.value is not None:
            allowed.add(abs(metric.value))
    return allowed


def _news_numbers(news: tuple[NewsItem, ...]) -> set[float]:
    return {value for item in news for _, value in extract_numbers(f"{item.title} {item.snippet}")}


def _is_allowed(value: float, computed: set[float], from_news: set[float]) -> bool:
    if any(abs(value - known) <= NUMBER_TOLERANCE + FLOAT_EPSILON for known in computed):
        return True
    return any(abs(value - known) <= FLOAT_EPSILON for known in from_news)


def extract_urls(text: str) -> list[str]:
    """URLs written in the text, without trailing punctuation."""
    return [url.rstrip(TRAILING_URL_PUNCTUATION) for url in _URL.findall(text)]


def check_citations(text: str, news: tuple[NewsItem, ...]) -> list[str]:
    """Every URL in the text must be one of the retrieved news URLs."""
    retrieved = {_normalize_url(item.url) for item in news}
    return [
        f"URL is not among the retrieved sources: {url}"
        for url in extract_urls(text)
        if _normalize_url(url) not in retrieved
    ]


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


def check_sections(text: str) -> list[str]:
    """Every required section must appear as a markdown heading."""
    headings = {normalize(heading) for heading in _HEADING.findall(text)}
    return [
        f"Required section is missing: {section}"
        for section in REQUIRED_REPORT_SECTIONS
        if normalize(section) not in headings
    ]


def check_disclaimer(text: str) -> list[str]:
    """The medical disclaimer must appear in the text, word for word."""
    if " ".join(MEDICAL_DISCLAIMER.split()) in " ".join(text.split()):
        return []
    return ["The medical disclaimer is missing"]


def check_personal_data(text: str) -> list[str]:
    """No CPF, e-mail or phone number patterns."""
    return [
        f"Possible personal data ({label}) found in the text"
        for label, pattern in _PII_PATTERNS.items()
        if pattern.search(text)
    ]
