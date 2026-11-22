import re
from datetime import date

import pytest

from srag.formatting import (
    format_count,
    format_date,
    format_percent,
    scope_name,
)
from srag.guardrails.output import extract_numbers


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (4.489, "4,5%"),
        (-14.434, "-14,4%"),
        (0.0, "0,0%"),
        (-0.04, "0,0%"),
        (100.0, "100,0%"),
        (52.7, "52,7%"),
        (0.05, "0,1%"),
    ],
)
def test_format_percent_uses_one_decimal_and_a_comma(value, expected):
    assert format_percent(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(0, "0"), (337, "337"), (14233, "14.233"), (1234567, "1.234.567")]
)
def test_format_count_separates_thousands_with_dots(value, expected):
    assert format_count(value) == expected


def test_format_date_is_day_month_year():
    assert format_date(date(2026, 11, 5)) == "05/11/2026"


def test_scope_name():
    assert scope_name(None) == "Brasil"
    assert scope_name("SP") == "São Paulo (SP)"


def test_formatted_numbers_are_read_back_by_the_guardrail_number_parser():
    text = f"{format_percent(4.489)} e {format_count(14233)} e {format_count(37)}"

    assert [value for _, value in extract_numbers(text)] == [4.5, 14233.0, 37.0]
    assert re.fullmatch(r"\d+,\d%", format_percent(7.04))
