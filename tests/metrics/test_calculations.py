from datetime import date

import pytest

from srag.metrics.calculations import (
    CASE_GROWTH_RATE,
    COVID_VACCINATION_RATE,
    FLU_VACCINATION_RATE,
    ICU_ADMISSION_RATE,
    MORTALITY_RATE,
    Window,
    build_windows,
    case_growth_rate,
    covid_vaccination_rate,
    flu_vaccination_rate,
    icu_admission_rate,
    mortality_rate,
)

WINDOW = Window(start=date(2026, 10, 10), end=date(2026, 11, 8))
MIN_DENOMINATOR = 30


def test_build_windows_skips_lag_and_has_requested_size():
    current, previous = build_windows(date(2026, 11, 15), lag_days=7, window_days=30)

    assert current == Window(date(2026, 10, 10), date(2026, 11, 8))
    assert previous == Window(date(2026, 9, 10), date(2026, 10, 9))
    assert (current.end - current.start).days == 29


def test_build_windows_are_adjacent_without_overlap():
    current, previous = build_windows(date(2026, 3, 10), lag_days=0, window_days=3)

    assert (current.start - previous.end).days == 1


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [(150, 100, 50.0), (50, 100, -50.0), (100, 100, 0.0), (0, 100, -100.0)],
)
def test_growth_rate_values(current, previous, expected):
    result = case_growth_rate(current, previous, WINDOW, MIN_DENOMINATOR)

    assert result.name == CASE_GROWTH_RATE
    assert result.value == expected
    assert result.numerator == current
    assert result.denominator == previous
    assert not result.unstable


def test_growth_rate_is_undefined_when_previous_window_has_no_cases():
    result = case_growth_rate(40, 0, WINDOW, MIN_DENOMINATOR)

    assert result.value is None
    assert result.unstable


def test_growth_rate_is_unstable_when_previous_window_is_small():
    assert case_growth_rate(10, 29, WINDOW, MIN_DENOMINATOR).unstable
    assert not case_growth_rate(10, 30, WINDOW, MIN_DENOMINATOR).unstable


def test_mortality_counts_only_deaths_by_srag_over_closed_outcomes():
    counts = {1: 80, 2: 10, 3: 10, 9: 7}

    result = mortality_rate(counts, total_cases=120, window=WINDOW, min_denominator=30)

    assert result.name == MORTALITY_RATE
    assert result.numerator == 10
    assert result.denominator == 100
    assert result.value == 10.0
    assert result.completeness == pytest.approx(100 / 120)


def test_mortality_is_undefined_when_every_outcome_is_ignored_or_open():
    result = mortality_rate({}, total_cases=50, window=WINDOW, min_denominator=30)

    assert result.value is None
    assert result.denominator == 0
    assert result.completeness == 0.0
    assert result.unstable


def test_rate_with_no_cases_at_all_has_zero_completeness():
    result = icu_admission_rate({}, total_cases=0, window=WINDOW, min_denominator=30)

    assert result.value is None
    assert result.completeness == 0.0


def test_rate_is_unstable_when_denominator_is_below_minimum():
    small = mortality_rate({1: 20, 2: 9}, 29, WINDOW, MIN_DENOMINATOR)
    enough = mortality_rate({1: 21, 2: 9}, 30, WINDOW, MIN_DENOMINATOR)

    assert small.unstable
    assert not enough.unstable


def test_icu_rate_ignores_codes_that_are_not_yes_or_no():
    result = icu_admission_rate({1: 30, 2: 70, 9: 20}, 120, WINDOW, MIN_DENOMINATOR)

    assert result.name == ICU_ADMISSION_RATE
    assert result.value == 30.0
    assert result.denominator == 100


def test_vaccination_rates_use_their_own_columns_and_names():
    covid = covid_vaccination_rate({1: 60, 2: 40}, 100, WINDOW, MIN_DENOMINATOR)
    flu = flu_vaccination_rate({1: 25, 2: 75}, 100, WINDOW, MIN_DENOMINATOR)

    assert (covid.name, covid.value) == (COVID_VACCINATION_RATE, 60.0)
    assert (flu.name, flu.value) == (FLU_VACCINATION_RATE, 25.0)


def test_results_carry_the_window_and_a_limitation_note():
    result = covid_vaccination_rate({1: 1, 2: 1}, 2, WINDOW, MIN_DENOMINATOR)

    assert (result.window_start, result.window_end) == (WINDOW.start, WINDOW.end)
    assert "população" in result.note
