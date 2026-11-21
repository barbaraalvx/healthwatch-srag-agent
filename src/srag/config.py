"""Application settings loaded from environment variables and the optional .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

VALID_UFS: tuple[str, ...] = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)  # fmt: skip

NEWS_ALLOWED_DOMAINS: tuple[str, ...] = (
    "gov.br",
    "fiocruz.br",
    "agenciabrasil.ebc.com.br",
    "g1.globo.com",
    "folha.uol.com.br",
    "estadao.com.br",
    "cnnbrasil.com.br",
    "bbc.com",
    "paho.org",
    "who.int",
)


class Settings(BaseSettings):
    """All tunable values of the project. Secrets are never printed (SecretStr)."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: SecretStr = SecretStr("")
    tavily_api_key: SecretStr = SecretStr("")

    llm_model: str = "claude-haiku-5-5"
    llm_temperature: float = Field(default=0, ge=0, le=1)
    llm_max_tokens: int = Field(default=2000, gt=0)
    llm_timeout_seconds: int = Field(default=60, gt=0)
    llm_price_input_per_mtok: float = Field(default=0.10, ge=0)
    llm_price_output_per_mtok: float = Field(default=0.50, ge=0)

    agent_max_iterations: int = Field(default=8, gt=0)
    max_cost_usd_per_run: float = Field(default=0.10, gt=0)

    news_max_results: int = Field(default=5, gt=0)
    news_days: int = Field(default=30, gt=0)

    report_lag_days: int = Field(default=7, ge=0)
    min_denominator: int = Field(default=30, gt=0)

    data_raw_dir: Path = Path("data/raw")
    data_processed_path: Path = Path("data/processed/srag.parquet")
    reports_dir: Path = Path("reports")

    log_level: str = "INFO"

    @field_validator("data_raw_dir", "data_processed_path", "reports_dir")
    @classmethod
    def resolve_from_project_root(cls, path: Path) -> Path:
        """Anchor relative paths to the project root, never to the current directory."""
        return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
