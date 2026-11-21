"""Computes every report metric for one scope (Brazil or a UF) from the case repository."""

from dataclasses import dataclass
from datetime import date

from srag.config import Settings
from srag.data import schema
from srag.data.repository import CaseRepository, NoCasesError
from srag.metrics.calculations import (
    MetricResult,
    Window,
    build_windows,
    case_growth_rate,
    covid_vaccination_rate,
    flu_vaccination_rate,
    icu_admission_rate,
    mortality_rate,
)


@dataclass(frozen=True)
class MetricsSnapshot:
    uf: str | None
    reference_date: date
    current_window: Window
    previous_window: Window
    metrics: tuple[MetricResult, ...]


def compute_metrics(
    repository: CaseRepository, uf: str | None, settings: Settings
) -> MetricsSnapshot:
    """Compute all metrics, anchored on the latest case date of the scope."""
    reference_date = repository.max_case_date(uf)
    if reference_date is None:
        raise NoCasesError(f"No cases found for scope {uf or 'BR'}")
    current, previous = build_windows(
        reference_date, settings.report_lag_days, settings.metric_window_days
    )
    min_denominator = settings.min_denominator
    total = repository.count_cases(uf, current.start, current.end)

    def counts(column: str) -> dict[int, int]:
        return repository.count_cases_by_code(uf, column, current.start, current.end)

    metrics = (
        case_growth_rate(
            total,
            repository.count_cases(uf, previous.start, previous.end),
            current,
            min_denominator,
        ),
        mortality_rate(counts(schema.OUTCOME), total, current, min_denominator),
        icu_admission_rate(counts(schema.ICU), total, current, min_denominator),
        covid_vaccination_rate(counts(schema.COVID_VACCINE), total, current, min_denominator),
        flu_vaccination_rate(counts(schema.FLU_VACCINE), total, current, min_denominator),
    )
    return MetricsSnapshot(uf, reference_date, current, previous, metrics)
