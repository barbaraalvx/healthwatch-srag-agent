"""Builds the text the writer LLM receives: computed metrics plus the untrusted news block."""

from srag.formatting import (
    METRIC_LABELS,
    format_count,
    format_date,
    format_percent,
    scope_name,
)
from srag.metrics.calculations import CASE_GROWTH_RATE, MetricResult
from srag.metrics.snapshot import MetricsSnapshot

UNSTABLE_FLAG = "[AMOSTRA PEQUENA: resultado instável]"


def build_writer_input(snapshot: MetricsSnapshot, news_block: str) -> str:
    """The full user message for the writer. Only aggregated, already computed values."""
    current, previous = snapshot.current_window, snapshot.previous_window
    window_days = (current.end - current.start).days + 1
    lag_days = (snapshot.reference_date - current.end).days
    lines = [
        f"Escopo: {scope_name(snapshot.uf)}",
        f"Data de referência dos dados: {format_date(snapshot.reference_date)} "
        "(último caso com início de sintomas).",
        f"Janela atual: {format_date(current.start)} a {format_date(current.end)} "
        f"({window_days} dias, sem os últimos {lag_days} dias por atraso de notificação). "
        f"Janela anterior: {format_date(previous.start)} a {format_date(previous.end)}.",
        "",
        "Métricas calculadas (copie os números exatamente como estão):",
        *(describe_metric(metric) for metric in snapshot.metrics),
        "",
        "Notícias:",
        news_block,
    ]
    return "\n".join(lines)


def describe_metric(metric: MetricResult) -> str:
    """One line per metric, with the value, its basis, flags and the limitation note."""
    label = METRIC_LABELS[metric.name]
    detail = _growth_detail(metric) if metric.name == CASE_GROWTH_RATE else _rate_detail(metric)
    parts = [f"- {label}: {detail}"]
    if metric.unstable:
        parts.append(UNSTABLE_FLAG)
    if metric.note:
        parts.append(f"Nota: {metric.note}")
    return " ".join(parts)


def _growth_detail(metric: MetricResult) -> str:
    if metric.value is None:
        return "indefinida (a janela anterior não teve casos)."
    return (
        f"{format_percent(metric.value)} ({format_count(metric.numerator)} casos na janela "
        f"atual contra {format_count(metric.denominator)} na anterior)."
    )


def _rate_detail(metric: MetricResult) -> str:
    completeness = format_percent(metric.completeness * 100)
    if metric.value is None:
        return "indefinida (nenhum caso com informação conhecida)."
    return (
        f"{format_percent(metric.value)} ({format_count(metric.numerator)} de "
        f"{format_count(metric.denominator)} casos com informação conhecida; "
        f"completude de {completeness})."
    )
