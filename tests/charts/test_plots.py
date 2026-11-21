from datetime import date
from pathlib import Path

import pytest

from srag.charts.plots import daily_cases_chart, monthly_cases_chart, scope_label
from srag.charts.series import CaseSeries, daily_points, monthly_points

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REFERENCE_DATE = date(2026, 11, 15)


@pytest.fixture
def daily_series() -> CaseSeries:
    counts = {date(2026, 11, day): day * 10 for day in range(1, 16)}
    return CaseSeries(None, REFERENCE_DATE, daily_points(counts, REFERENCE_DATE, 30, 7))


@pytest.fixture
def monthly_series() -> CaseSeries:
    counts = {date(2026, 5, 1): 39_589, date(2026, 11, 1): 3_900}
    return CaseSeries("SP", REFERENCE_DATE, monthly_points(counts, REFERENCE_DATE, 12))


def test_scope_label():
    assert scope_label(None) == "Brasil"
    assert scope_label("SP") == "UF SP"


def test_daily_chart_creates_a_png_file(daily_series, tmp_path: Path):
    output = daily_cases_chart(daily_series, tmp_path / "daily.png")

    assert output == tmp_path / "daily.png"
    assert output.read_bytes().startswith(PNG_SIGNATURE)


def test_monthly_chart_creates_a_png_file_and_missing_folders(monthly_series, tmp_path: Path):
    output = monthly_cases_chart(monthly_series, tmp_path / "nested" / "monthly.png")

    assert output.read_bytes().startswith(PNG_SIGNATURE)


def test_charts_handle_a_scope_without_any_case_in_the_window(tmp_path: Path):
    empty = CaseSeries("AC", REFERENCE_DATE, daily_points({}, REFERENCE_DATE, 30, 7))

    assert daily_cases_chart(empty, tmp_path / "empty.png").exists()
