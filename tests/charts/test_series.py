from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from srag.charts.series import (
    build_daily_series,
    build_monthly_series,
    daily_points,
    monthly_points,
)
from srag.config import DAILY_CHART_DAYS, MONTHLY_CHART_MONTHS, Settings
from srag.data import schema
from srag.data.repository import CaseRepository, NoCasesError


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, report_lag_days=7)


@pytest.fixture
def repository(tmp_path: Path) -> CaseRepository:
    dates = ["2025-12-05", "2026-01-31", "2026-02-01", "2026-02-02", "2026-02-02", "2026-02-10"]
    frame = pd.DataFrame(
        {schema.CASE_DATE: pd.to_datetime(dates), schema.UF: ["SP", "SP", "RJ", "SP", "SP", "SP"]}
    )
    path = tmp_path / "srag.parquet"
    frame.to_parquet(path, index=False)
    with CaseRepository(path) as repo:
        yield repo


def test_daily_points_fill_missing_days_with_zero():
    counts = {date(2026, 3, 7): 3, date(2026, 3, 10): 1}

    points = daily_points(counts, date(2026, 3, 10), days=5, lag_days=2)

    assert [point.period_start for point in points] == [date(2026, 3, day) for day in range(6, 11)]
    assert [point.cases for point in points] == [0, 3, 0, 0, 1]


def test_daily_points_flag_the_last_lag_days_as_incomplete():
    points = daily_points({}, date(2026, 3, 10), days=5, lag_days=2)

    assert [point.incomplete for point in points] == [False, False, False, True, True]


def test_daily_points_without_lag_have_no_incomplete_day():
    points = daily_points({}, date(2026, 3, 10), days=5, lag_days=0)

    assert not any(point.incomplete for point in points)


def test_monthly_points_cross_the_year_boundary_in_order():
    points = monthly_points({}, date(2026, 2, 15), months=4)

    assert [point.period_start for point in points] == [
        date(2025, 11, 1),
        date(2025, 12, 1),
        date(2026, 1, 1),
        date(2026, 2, 1),
    ]


def test_monthly_points_flag_only_the_reference_month_when_partial():
    points = monthly_points({}, date(2026, 2, 15), months=4)

    assert [point.incomplete for point in points] == [False, False, False, True]


@pytest.mark.parametrize("last_day", [date(2026, 2, 28), date(2028, 2, 29), date(2026, 3, 31)])
def test_monthly_points_are_complete_when_reference_is_the_last_day_of_month(last_day):
    assert not monthly_points({}, last_day, months=3)[-1].incomplete


def test_monthly_points_use_counts_and_zero_fill():
    counts = {date(2026, 1, 1): 7}

    points = monthly_points(counts, date(2026, 2, 15), months=3)

    assert [point.cases for point in points] == [0, 7, 0]


def test_daily_series_has_30_points_ending_at_the_reference_date(repository, settings):
    series = build_daily_series(repository, None, settings)

    assert len(series.points) == DAILY_CHART_DAYS
    assert series.reference_date == date(2026, 2, 10)
    assert series.points[-1].period_start == date(2026, 2, 10)
    assert sum(point.cases for point in series.points) == 5


def test_daily_series_for_a_state_excludes_other_states(repository, settings):
    series = build_daily_series(repository, "RJ", settings)

    assert series.reference_date == date(2026, 2, 1)
    assert sum(point.cases for point in series.points) == 1


def test_monthly_series_has_12_months_and_counts_each_month(repository):
    series = build_monthly_series(repository, None)
    cases_by_month = {point.period_start: point.cases for point in series.points}

    assert len(series.points) == MONTHLY_CHART_MONTHS
    assert series.points[0].period_start == date(2025, 3, 1)
    assert cases_by_month[date(2025, 12, 1)] == 1
    assert cases_by_month[date(2026, 1, 1)] == 1
    assert cases_by_month[date(2026, 2, 1)] == 4
    assert series.points[-1].incomplete


def test_series_raise_when_scope_has_no_cases(repository, settings):
    with pytest.raises(NoCasesError):
        build_daily_series(repository, "AC", settings)
    with pytest.raises(NoCasesError):
        build_monthly_series(repository, "AC")
