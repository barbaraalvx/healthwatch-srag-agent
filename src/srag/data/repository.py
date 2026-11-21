"""Fixed, parameterized, read-only queries over the cleaned SRAG data (no free-form SQL)."""

from datetime import date
from pathlib import Path
from types import TracebackType

import duckdb

from srag.data import schema

# Matches every row when uf is None (all of Brazil); the value is always a bound parameter.
_UF_FILTER = f"(CAST(? AS VARCHAR) IS NULL OR {schema.UF} = ?)"
_SCOPE_FILTER = f"{_UF_FILTER} AND {schema.CASE_DATE} BETWEEN ? AND ?"


class NoCasesError(LookupError):
    """Raised when the selected scope has no cases at all."""


class CaseRepository:
    """Loads the Parquet file into memory, then locks the connection against any file access."""

    def __init__(self, parquet_path: Path) -> None:
        self._connection = duckdb.connect(":memory:")
        self._connection.execute(
            f"CREATE TABLE cases AS SELECT * REPLACE "
            f"(CAST({schema.CASE_DATE} AS DATE) AS {schema.CASE_DATE}) FROM read_parquet(?)",
            [str(parquet_path)],
        )
        self._connection.execute("SET enable_external_access = false")
        self._connection.execute("SET lock_configuration = true")

    def max_case_date(self, uf: str | None) -> date | None:
        """Most recent case date in the scope, or None when there are no cases."""
        row = self._connection.execute(
            f"SELECT max({schema.CASE_DATE}) FROM cases WHERE {_UF_FILTER}", [uf, uf]
        ).fetchone()
        return row[0] if row else None

    def count_cases(self, uf: str | None, start: date, end: date) -> int:
        """Total cases between start and end (inclusive)."""
        row = self._connection.execute(
            f"SELECT count(*) FROM cases WHERE {_SCOPE_FILTER}", [uf, uf, start, end]
        ).fetchone()
        return row[0] if row else 0

    def count_cases_by_code(
        self, uf: str | None, column: str, start: date, end: date
    ) -> dict[int, int]:
        """Cases per known code of a coded column; missing values are not counted."""
        if column not in schema.VALID_CODES:
            raise ValueError(f"Not a coded column: {column}")
        rows = self._connection.execute(
            f"SELECT {column}, count(*) FROM cases "
            f"WHERE {_SCOPE_FILTER} AND {column} IS NOT NULL GROUP BY {column}",
            [uf, uf, start, end],
        ).fetchall()
        return {code: count for code, count in rows}

    def count_cases_by_day(self, uf: str | None, start: date, end: date) -> dict[date, int]:
        """Cases per day between start and end (inclusive); days without cases are omitted."""
        rows = self._connection.execute(
            f"SELECT {schema.CASE_DATE}, count(*) FROM cases WHERE {_SCOPE_FILTER} "
            f"GROUP BY {schema.CASE_DATE} ORDER BY {schema.CASE_DATE}",
            [uf, uf, start, end],
        ).fetchall()
        return {day: count for day, count in rows}

    def count_cases_by_month(self, uf: str | None, start: date, end: date) -> dict[date, int]:
        """Cases per calendar month (keyed by its first day); months without cases are omitted."""
        rows = self._connection.execute(
            f"SELECT CAST(date_trunc('month', {schema.CASE_DATE}) AS DATE) AS month, count(*) "
            f"FROM cases WHERE {_SCOPE_FILTER} GROUP BY month ORDER BY month",
            [uf, uf, start, end],
        ).fetchall()
        return {month: count for month, count in rows}

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CaseRepository":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
