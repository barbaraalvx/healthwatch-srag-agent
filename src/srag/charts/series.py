"""Chart data: zero-filled daily and monthly case series, with incomplete periods flagged."""

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from srag.config import DAILY_CHART_DAYS, MONTHLY_CHART_MONTHS, Settings
from srag.data.repository import CaseRepository, NoCasesError


@dataclass(frozen=True)
class SeriesPoint:
    period_start: date
    cases: int
    incomplete: bool


@dataclass(frozen=True)
class CaseSeries:
    uf: str | None
    reference_date: date
    points: tuple[SeriesPoint, ...]


def daily_points(
    counts: Mapping[date, int], reference_date: date, days: int, lag_days: int
) -> tuple[SeriesPoint, ...]:
    """The last `days` days ending at the reference date; the last `lag_days` are incomplete."""
    first_day = reference_date - timedelta(days=days - 1)
    last_complete_day = reference_date - timedelta(days=lag_days)
    points = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        points.append(SeriesPoint(day, counts.get(day, 0), incomplete=day > last_complete_day))
    return tuple(points)


def monthly_points(
    counts: Mapping[date, int], reference_date: date, months: int
) -> tuple[SeriesPoint, ...]:
    """The last `months` calendar months; the reference month is partial unless it has ended."""
    current_month = reference_date.replace(day=1)
    month_is_partial = (
        reference_date.day != calendar.monthrange(reference_date.year, reference_date.month)[1]
    )
    starts = [_shift_months(current_month, -back) for back in range(months - 1, -1, -1)]
    return tuple(
        SeriesPoint(
            start, counts.get(start, 0), incomplete=month_is_partial and start == current_month
        )
        for start in starts
    )


def _shift_months(month_start: date, months: int) -> date:
    index = month_start.year * 12 + month_start.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def build_daily_series(
    repository: CaseRepository, uf: str | None, settings: Settings
) -> CaseSeries:
    """Daily cases for the last DAILY_CHART_DAYS days of the scope."""
    reference_date = _reference_date(repository, uf)
    start = reference_date - timedelta(days=DAILY_CHART_DAYS - 1)
    counts = repository.count_cases_by_day(uf, start, reference_date)
    points = daily_points(counts, reference_date, DAILY_CHART_DAYS, settings.report_lag_days)
    return CaseSeries(uf, reference_date, points)


def build_monthly_series(repository: CaseRepository, uf: str | None) -> CaseSeries:
    """Monthly cases for the last MONTHLY_CHART_MONTHS months of the scope."""
    reference_date = _reference_date(repository, uf)
    points = monthly_points(
        repository.count_cases_by_month(uf, _first_month(reference_date), reference_date),
        reference_date,
        MONTHLY_CHART_MONTHS,
    )
    return CaseSeries(uf, reference_date, points)


def _first_month(reference_date: date) -> date:
    return _shift_months(reference_date.replace(day=1), -(MONTHLY_CHART_MONTHS - 1))


def _reference_date(repository: CaseRepository, uf: str | None) -> date:
    reference_date = repository.max_case_date(uf)
    if reference_date is None:
        raise NoCasesError(f"No cases found for scope {uf or 'BR'}")
    return reference_date
