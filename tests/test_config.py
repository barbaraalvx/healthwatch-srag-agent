import pytest
from pydantic import ValidationError

from srag.config import NEWS_ALLOWED_DOMAINS, PROJECT_ROOT, VALID_UFS, Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def test_default_values_match_documented_defaults(settings: Settings):
    assert settings.llm_model == "claude-haiku-5-5"
    assert settings.report_lag_days == 7
    assert settings.min_denominator == 30
    assert settings.news_days == 30


def test_there_are_27_unique_ufs():
    assert len(VALID_UFS) == 27
    assert len(set(VALID_UFS)) == 27


def test_news_domains_are_not_empty():
    assert "fiocruz.br" in NEWS_ALLOWED_DOMAINS


def test_relative_paths_are_anchored_to_project_root(settings: Settings):
    assert settings.reports_dir == PROJECT_ROOT / "reports"
    assert settings.data_processed_path == PROJECT_ROOT / "data" / "processed" / "srag.parquet"


def test_api_keys_are_masked_when_printed():
    settings = Settings(_env_file=None, anthropic_api_key="sk-ant-secret")

    assert "sk-ant-secret" not in repr(settings)
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-secret"


def test_invalid_temperature_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_temperature=2)
