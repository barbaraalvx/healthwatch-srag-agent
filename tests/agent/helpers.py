"""Builders shared by the agent tests."""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from srag.agent.dependencies import AgentDependencies
from srag.audit.logger import AuditLogger
from srag.config import Settings
from srag.data import schema
from srag.data.repository import CaseRepository
from srag.formatting import format_percent
from srag.guardrails.limits import RunLimits
from srag.metrics.calculations import CASE_GROWTH_RATE, MORTALITY_RATE
from srag.metrics.snapshot import MetricsSnapshot

TODAY = date(2026, 11, 21)
REFERENCE_DATE = date(2026, 11, 15)


def synthetic_cases() -> pd.DataFrame:
    """Cases for SP and RJ from 2026-09-10 to the reference date, with mixed outcomes."""
    rows = []
    day = date(2026, 9, 10)
    index = 0
    while day <= REFERENCE_DATE:
        cases_today = 3 if day <= date(2026, 10, 9) else 2
        for _ in range(cases_today):
            rows.append(
                {
                    schema.CASE_DATE: pd.Timestamp(day),
                    schema.UF: "SP" if index % 5 else "RJ",
                    schema.ICU: 1 if index % 4 == 0 else 2,
                    schema.OUTCOME: 2 if index % 10 == 0 else (1 if index % 3 else None),
                    schema.COVID_VACCINE: 1 if index % 2 == 0 else 2,
                    schema.FLU_VACCINE: 1 if index % 5 == 0 else 2,
                }
            )
            index += 1
        day += timedelta(days=1)
    frame = pd.DataFrame(rows)
    for column in (schema.ICU, schema.OUTCOME, schema.COVID_VACCINE, schema.FLU_VACCINE):
        frame[column] = frame[column].astype("Int8")
    return frame


def make_deps(
    tmp_path: Path,
    repository: CaseRepository,
    llm,
    searcher,
    settings: Settings,
    clock=None,
) -> AgentDependencies:
    audit = AuditLogger.create(tmp_path / "reports")
    limits = RunLimits(settings, clock) if clock else RunLimits(settings)
    return AgentDependencies(
        settings=settings,
        repository=repository,
        searcher=searcher,
        llm=llm,
        audit=audit,
        limits=limits,
        charts_dir=audit.run_dir / "charts",
        today=TODAY,
    )


def metric_value(snapshot: MetricsSnapshot, name: str) -> float:
    return next(m.value for m in snapshot.metrics if m.name == name)


def valid_report_text(snapshot: MetricsSnapshot, news_url: str | None = None) -> str:
    """A writer answer that passes the output guardrail for this snapshot."""
    drop = format_percent(abs(metric_value(snapshot, CASE_GROWTH_RATE)))
    mortality = format_percent(metric_value(snapshot, MORTALITY_RATE))
    lines = [
        "## Resumo executivo",
        f"Os casos de SRAG tiveram queda de {drop}. A letalidade foi de {mortality}.",
        "",
        "## Análise do cenário",
        "Os dados vão até a data de referência e as métricas de UTI e vacinação são proxies.",
    ]
    if news_url:
        lines.append(f"A Fiocruz aponta sinal de crescimento ([Fiocruz]({news_url})).")
    else:
        lines.append("Nenhuma notícia confiável foi encontrada.")
    return "\n".join(lines)


def invalid_report_text() -> str:
    """A writer answer with an invented number, so the output guardrail rejects it."""
    return (
        "## Resumo executivo\nForam registrados 4.321 óbitos.\n\n"
        "## Análise do cenário\nTexto com número inventado."
    )
