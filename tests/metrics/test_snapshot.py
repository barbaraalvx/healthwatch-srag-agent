from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from srag.config import Settings
from srag.data import schema
from srag.data.repository import CaseRepository
from srag.metrics.calculations import (
    CASE_GROWTH_RATE,
    COVID_VACCINATION_RATE,
    FLU_VACCINATION_RATE,
    ICU_ADMISSION_RATE,
    MORTALITY_RATE,
    Window,
)
from srag.metrics.snapshot import NoCasesError, compute_metrics

# Columns: case date, outcome, icu, covid vaccine, flu vaccine (None = missing).
CASES = [
    ("2026-03-10", 2, 1, 1, None),  # inside the reporting lag: must be ignored
    ("2026-03-09", 2, 1, 1, None),  # inside the reporting lag: must be ignored
    ("2026-03-08", None, None, None, None),  # current window, everything ignored
    ("2026-03-07", 1, 2, 2, None),
    ("2026-03-07", 1, 2, 1, None),
    ("2026-03-06", 2, 1, 1, None),
    ("2026-03-05", 1, 2, 2, None),  # previous window
    ("2026-03-03", 1, 2, 2, None),  # previous window
    ("2026-03-02", 2, 1, 1, None),  # before the previous window: must be ignored
]


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, report_lag_days=2, metric_window_days=3, min_denominator=1)


@pytest.fixture
def repository(tmp_path: Path) -> CaseRepository:
    frame = pd.DataFrame(
        CASES,
        columns=[
            schema.CASE_DATE,
            schema.OUTCOME,
            schema.ICU,
            schema.COVID_VACCINE,
            schema.FLU_VACCINE,
        ],
    )
    frame[schema.CASE_DATE] = pd.to_datetime(frame[schema.CASE_DATE])
    frame[schema.UF] = "SP"
    for column in (schema.OUTCOME, schema.ICU, schema.COVID_VACCINE, schema.FLU_VACCINE):
        frame[column] = frame[column].astype("Int8")
    path = tmp_path / "srag.parquet"
    frame.to_parquet(path, index=False)
    with CaseRepository(path) as repo:
        yield repo


def test_snapshot_anchors_windows_on_latest_date_minus_lag(repository, settings):
    snapshot = compute_metrics(repository, None, settings)

    assert snapshot.reference_date == date(2026, 3, 10)
    assert snapshot.current_window == Window(date(2026, 3, 6), date(2026, 3, 8))
    assert snapshot.previous_window == Window(date(2026, 3, 3), date(2026, 3, 5))


def test_snapshot_values_match_hand_calculation(repository, settings):
    snapshot = compute_metrics(repository, None, settings)
    by_name = {metric.name: metric for metric in snapshot.metrics}

    assert by_name[CASE_GROWTH_RATE].value == 100.0  # 4 cases now, 2 before
    assert by_name[MORTALITY_RATE].value == pytest.approx(100 / 3)  # 1 death, 3 closed
    assert by_name[MORTALITY_RATE].completeness == 0.75
    assert by_name[ICU_ADMISSION_RATE].value == pytest.approx(100 / 3)
    assert by_name[COVID_VACCINATION_RATE].value == pytest.approx(200 / 3)
    assert by_name[FLU_VACCINATION_RATE].value is None


def test_snapshot_for_state_matches_brazil_when_all_cases_are_from_that_state(repository, settings):
    brazil = compute_metrics(repository, None, settings)
    state = compute_metrics(repository, "SP", settings)

    assert state.metrics == brazil.metrics


def test_snapshot_raises_when_scope_has_no_cases(repository, settings):
    with pytest.raises(NoCasesError):
        compute_metrics(repository, "AC", settings)
