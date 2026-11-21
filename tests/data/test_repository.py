from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from srag.data import schema
from srag.data.repository import CaseRepository


@pytest.fixture
def repository(tmp_path: Path) -> CaseRepository:
    cases = pd.DataFrame(
        {
            schema.CASE_DATE: pd.to_datetime(
                ["2026-01-10", "2026-01-10", "2026-01-11", "2026-01-20"]
            ),
            schema.UF: ["SP", "RJ", "SP", "SP"],
            schema.ICU: pd.array([1, 2, None, 1], dtype="Int8"),
        }
    )
    path = tmp_path / "srag.parquet"
    cases.to_parquet(path, index=False)
    with CaseRepository(path) as repo:
        yield repo


def test_max_case_date_for_brazil(repository: CaseRepository):
    assert repository.max_case_date(None) == date(2026, 1, 20)


def test_max_case_date_for_one_state(repository: CaseRepository):
    assert repository.max_case_date("RJ") == date(2026, 1, 10)


def test_max_case_date_is_none_when_scope_has_no_cases(repository: CaseRepository):
    assert repository.max_case_date("AC") is None


def test_count_cases_by_day_for_brazil(repository: CaseRepository):
    counts = repository.count_cases_by_day(None, date(2026, 1, 10), date(2026, 1, 11))

    assert counts == {date(2026, 1, 10): 2, date(2026, 1, 11): 1}


def test_count_cases_by_day_for_one_state_excludes_other_states(repository: CaseRepository):
    counts = repository.count_cases_by_day("SP", date(2026, 1, 1), date(2026, 1, 31))

    assert counts == {date(2026, 1, 10): 1, date(2026, 1, 11): 1, date(2026, 1, 20): 1}


def test_uf_value_is_bound_as_parameter_not_executed_as_sql(repository: CaseRepository):
    counts = repository.count_cases_by_day("SP' OR '1'='1", date(2026, 1, 1), date(2026, 1, 31))

    assert counts == {}


def test_connection_cannot_read_files_or_change_settings(repository: CaseRepository):
    connection = repository._connection

    with pytest.raises(duckdb.Error):
        connection.execute("SELECT * FROM read_csv('anything.csv')")
    with pytest.raises(duckdb.Error):
        connection.execute("SET enable_external_access = true")


def test_count_cases_by_scope(repository: CaseRepository):
    assert repository.count_cases(None, date(2026, 1, 10), date(2026, 1, 11)) == 3
    assert repository.count_cases("SP", date(2026, 1, 10), date(2026, 1, 11)) == 2
    assert repository.count_cases("AC", date(2026, 1, 1), date(2026, 1, 31)) == 0


def test_count_cases_by_code_leaves_missing_values_out(repository: CaseRepository):
    counts = repository.count_cases_by_code(None, schema.ICU, date(2026, 1, 1), date(2026, 1, 31))

    assert counts == {1: 2, 2: 1}


@pytest.mark.parametrize("column", [schema.UF, "icu; DROP TABLE cases", "unknown"])
def test_count_cases_by_code_rejects_columns_that_are_not_coded(
    repository: CaseRepository, column: str
):
    with pytest.raises(ValueError):
        repository.count_cases_by_code(None, column, date(2026, 1, 1), date(2026, 1, 31))
