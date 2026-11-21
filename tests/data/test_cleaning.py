from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from srag.data import schema
from srag.data.cleaning import (
    DROPPED_DATE_OUT_OF_RANGE,
    DROPPED_DUPLICATE,
    DROPPED_INVALID_DATE,
    clean,
    parse_case_dates,
    to_age_band,
    to_known_code,
    validate_uf,
)

SAMPLE_CSV = Path(__file__).parents[1] / "fixtures" / "srag_sample.csv"
TODAY = date(2026, 6, 1)


@pytest.fixture
def raw() -> pd.DataFrame:
    return pd.read_csv(SAMPLE_CSV, sep=";", dtype=str)


def test_parse_case_dates_turns_invalid_values_into_missing():
    parsed = parse_case_dates(pd.Series(["2026-01-10T00:00:00.000Z", "not-a-date", None]))

    assert parsed.iloc[0] == pd.Timestamp("2026-01-10")
    assert parsed.iloc[1:].isna().all()


@pytest.mark.parametrize("raw_value", ["9", "3", "", "abc", None])
def test_to_known_code_drops_ignored_and_unexpected_values(raw_value):
    result = to_known_code(pd.Series([raw_value]), (1, 2))

    assert result.isna().all()


def test_to_known_code_keeps_valid_values():
    result = to_known_code(pd.Series(["1", "2"]), (1, 2))

    assert result.tolist() == [1, 2]


def test_validate_uf_keeps_only_official_codes():
    result = validate_uf(pd.Series(["SP", "XX", None]))

    assert result.iloc[0] == "SP"
    assert result.iloc[1:].isna().all()


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        ("30", "3", "18-39"),
        ("3", "2", "0-4"),
        ("20", "1", "0-4"),
        ("60", "2", "5-11"),
        ("85", "3", "80+"),
        ("200", "3", None),
        ("-1", "3", None),
        ("30", "9", None),
        ("", "3", None),
    ],
)
def test_to_age_band(value, unit, expected):
    band = to_age_band(pd.Series([value]), pd.Series([unit])).iloc[0]

    assert (pd.isna(band) and expected is None) or band == expected


def test_clean_reports_each_dropped_reason(raw):
    result = clean(raw, TODAY)

    assert result.rows_read == 13
    assert result.dropped == {
        DROPPED_DUPLICATE: 1,
        DROPPED_INVALID_DATE: 1,
        DROPPED_DATE_OUT_OF_RANGE: 2,
    }
    assert len(result.cases) == 9


def test_clean_keeps_only_deidentified_columns(raw):
    result = clean(raw, TODAY)

    assert tuple(result.cases.columns) == schema.PROCESSED_COLUMNS


def test_clean_treats_ignored_code_as_missing(raw):
    cases = clean(raw, TODAY).cases

    row_with_ignored_icu = cases[cases[schema.OUTCOME] == 3].iloc[0]

    assert pd.isna(row_with_ignored_icu[schema.ICU])
    assert pd.isna(row_with_ignored_icu[schema.COVID_VACCINE])


def test_clean_keeps_case_with_unknown_uf_but_clears_the_uf(raw):
    cases = clean(raw, TODAY).cases

    assert cases[schema.UF].isna().sum() == 1
