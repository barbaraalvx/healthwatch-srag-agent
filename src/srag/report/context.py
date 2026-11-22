"""Turns the agent result into the plain values the HTML template shows."""

import base64
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from markupsafe import Markup

from srag.agent.graph import AgentResult
from srag.agent.state import STATUS_COMPLETED
from srag.config import MEDICAL_DISCLAIMER, REQUIRED_REPORT_SECTIONS
from srag.formatting import format_count, format_date, format_percent, scope_name
from srag.metrics.calculations import (
    CASE_GROWTH_RATE,
    COVID_VACCINATION_RATE,
    FLU_VACCINATION_RATE,
    ICU_ADMISSION_RATE,
    MORTALITY_RATE,
    MetricResult,
)
from srag.news.models import NewsItem
from srag.report.markup import markdown_to_html, split_sections
from srag.report.notes import LIMITATIONS

GENERATED_AT_FORMAT = "%d/%m/%Y %H:%M UTC"
NOT_AVAILABLE = "n/d"
UNDATED = "sem data de publicação"
AI_TEXT_UNAVAILABLE = (
    "O texto explicativo automático não está disponível nesta execução. "
    "As métricas e os gráficos abaixo foram calculados diretamente dos dados."
)

TREND_UP = "up"
TREND_DOWN = "down"
PRIMARY_METRICS = frozenset(
    {CASE_GROWTH_RATE, MORTALITY_RATE, ICU_ADMISSION_RATE, COVID_VACCINATION_RATE}
)
METRIC_ICONS: dict[str, str] = {
    CASE_GROWTH_RATE: "trend",
    MORTALITY_RATE: "pulse",
    ICU_ADMISSION_RATE: "bed",
    COVID_VACCINATION_RATE: "syringe",
    FLU_VACCINATION_RATE: "syringe",
}

METRIC_TITLES: dict[str, str] = {
    CASE_GROWTH_RATE: "Taxa de aumento de casos",
    MORTALITY_RATE: "Taxa de mortalidade",
    ICU_ADMISSION_RATE: "Taxa de ocupação de UTI (proxy)",
    COVID_VACCINATION_RATE: "Taxa de vacinação COVID-19 (proxy)",
    FLU_VACCINATION_RATE: "Taxa de vacinação gripe (proxy)",
}


@dataclass(frozen=True)
class MetricCard:
    title: str
    value: str
    basis: str
    window: str
    completeness: str | None
    unstable: bool
    note: str | None
    icon: str
    primary: bool
    trend: str | None


@dataclass(frozen=True)
class SourceLink:
    title: str
    url: str
    source: str
    published: str


@dataclass(frozen=True)
class RunDetails:
    """Provenance shown in the footer."""

    run_id: str
    generated_at: datetime
    model: str
    effort: str
    prompt_versions: dict[str, str]


@dataclass(frozen=True)
class ReportContext:
    scope: str
    reference_date: str
    window: str
    generated_at: str
    notice: str | None
    summary_markdown: str
    analysis_markdown: str
    summary_html: Markup
    analysis_html: Markup
    cards: tuple[MetricCard, ...]
    daily_chart_uri: str
    monthly_chart_uri: str
    limitations: tuple[str, ...]
    sources: tuple[SourceLink, ...]
    run: RunDetails
    status: str
    disclaimer: str


def build_report_context(result: AgentResult, run: RunDetails) -> ReportContext:
    """Collect everything the template needs, already formatted in pt-BR."""
    sections = split_sections(result.report_text.replace(MEDICAL_DISCLAIMER, ""))
    summary, analysis = (sections.get(title, "") for title in REQUIRED_REPORT_SECTIONS)
    return ReportContext(
        scope=scope_name(result.snapshot.uf),
        reference_date=format_date(result.snapshot.reference_date),
        window=_format_window(
            result.snapshot.current_window.start, result.snapshot.current_window.end
        ),
        generated_at=run.generated_at.strftime(GENERATED_AT_FORMAT),
        notice=None if result.status == STATUS_COMPLETED else AI_TEXT_UNAVAILABLE,
        summary_markdown=summary,
        analysis_markdown=analysis,
        summary_html=markdown_to_html(summary),
        analysis_html=markdown_to_html(analysis),
        cards=tuple(_metric_card(metric) for metric in result.snapshot.metrics),
        daily_chart_uri=_image_data_uri(result.daily_chart),
        monthly_chart_uri=_image_data_uri(result.monthly_chart),
        limitations=LIMITATIONS,
        sources=tuple(_source_link(item) for item in result.news_items),
        run=run,
        status=result.status,
        disclaimer=MEDICAL_DISCLAIMER,
    )


def _metric_card(metric: MetricResult) -> MetricCard:
    is_growth = metric.name == CASE_GROWTH_RATE
    return MetricCard(
        title=METRIC_TITLES[metric.name],
        value=NOT_AVAILABLE if metric.value is None else format_percent(metric.value),
        basis=_growth_basis(metric) if is_growth else _rate_basis(metric),
        window=_format_window(metric.window_start, metric.window_end),
        completeness=None if is_growth else format_percent(metric.completeness * 100),
        unstable=metric.unstable,
        note=metric.note,
        icon=METRIC_ICONS[metric.name],
        primary=metric.name in PRIMARY_METRICS,
        trend=_trend(metric) if is_growth else None,
    )


def _format_window(start: date, end: date) -> str:
    return f"{format_date(start)} a {format_date(end)}"


def _trend(metric: MetricResult) -> str | None:
    if metric.value is None or round(metric.value, 1) == 0:
        return None
    return TREND_UP if metric.value > 0 else TREND_DOWN


def _growth_basis(metric: MetricResult) -> str:
    if metric.value is None:
        return "A janela anterior não teve casos."
    return (
        f"{format_count(metric.numerator)} casos na janela atual "
        f"contra {format_count(metric.denominator)} na anterior"
    )


def _rate_basis(metric: MetricResult) -> str:
    return (
        f"{format_count(metric.numerator)} de {format_count(metric.denominator)} "
        "casos com informação conhecida"
    )


def _source_link(item: NewsItem) -> SourceLink:
    published = UNDATED if item.published_at is None else format_date(item.published_at)
    return SourceLink(item.title, item.url, item.source, published)


def _image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
