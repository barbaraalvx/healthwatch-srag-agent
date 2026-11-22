from pathlib import Path

import pytest

from srag.config import Settings
from srag.data.repository import CaseRepository
from srag.metrics.snapshot import MetricsSnapshot, compute_metrics
from tests.agent.helpers import synthetic_cases


@pytest.fixture
def repository(tmp_path: Path):
    path = tmp_path / "srag.parquet"
    synthetic_cases().to_parquet(path, index=False)
    with CaseRepository(path) as repo:
        yield repo


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, tavily_api_key="fake", anthropic_api_key="fake")


@pytest.fixture
def snapshot(repository, settings) -> MetricsSnapshot:
    return compute_metrics(repository, "SP", settings)
