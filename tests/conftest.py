from pathlib import Path

import pytest

from srag.config import Settings
from srag.data.repository import CaseRepository
from srag.metrics.snapshot import MetricsSnapshot, compute_metrics
from tests.agent.helpers import synthetic_cases, valid_report_text


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


REPORT_NEWS_URL = "https://agencia.fiocruz.br/infogripe-1"


@pytest.fixture
def service_settings(tmp_path: Path) -> Settings:
    parquet = tmp_path / "srag.parquet"
    synthetic_cases().to_parquet(parquet, index=False)
    return Settings(
        _env_file=None,
        anthropic_api_key="fake",
        tavily_api_key="fake",
        data_processed_path=parquet,
        reports_dir=tmp_path / "reports",
    )


@pytest.fixture
def writer_text(service_settings: Settings) -> str:
    with CaseRepository(service_settings.data_processed_path) as repository:
        snapshot = compute_metrics(repository, "SP", service_settings)
    return valid_report_text(snapshot, REPORT_NEWS_URL)
