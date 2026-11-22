"""Application settings loaded from environment variables and the optional .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

UF_NAMES: dict[str, str] = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso",
    "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná",
    "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte", "RO": "Rondônia", "RR": "Roraima",
    "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe", "SP": "São Paulo",
    "TO": "Tocantins",
}  # fmt: skip
VALID_UFS: tuple[str, ...] = tuple(UF_NAMES)

# Fixed by the assessment brief: daily chart over 30 days, monthly chart over 12 months.
DAILY_CHART_DAYS = 30
MONTHLY_CHART_MONTHS = 12

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

# International sources must mention Brazil (or the state); national ones are assumed Brazilian.
NEWS_INTERNATIONAL_DOMAINS: tuple[str, ...] = ("bbc.com", "paho.org", "who.int")

# Regex fragments (on accent-free, lower-case text) for news about SRAG and respiratory disease.
NEWS_TOPIC_PATTERNS: tuple[str, ...] = (
    r"srag",
    r"sindrome respirat",
    r"respirat",
    r"influenza",
    r"(?:info)?gripe",
    r"gripal",
    r"covid",
    r"coronavirus",
    r"sincicial",
    r"pneumonia",
    r"flu\b",
)
NEWS_COUNTRY_PATTERNS: tuple[str, ...] = (r"brasil", r"brazil")

ORCHESTRATOR_PROMPT = "orchestrator_v1"
WRITER_PROMPT = "writer_v1"
WRITER_MAX_ATTEMPTS = 2  # the first draft plus one retry with feedback
LLM_MAX_RETRIES = 1  # SDK retries on 429 and 5xx only; keep low to bound cost

MEDICAL_DISCLAIMER = (
    "Este relatório é informativo e não substitui avaliação, diagnóstico ou orientação de "
    "profissionais de saúde. As métricas de UTI e de vacinação são aproximações calculadas "
    "apenas entre casos notificados de SRAG."
)
REQUIRED_REPORT_SECTIONS: tuple[str, ...] = ("Resumo executivo", "Análise do cenário")
# Text rounds numbers, so a percentage may differ from the computed value by this many points.
NUMBER_TOLERANCE = 0.1

AUDIT_MAX_TEXT_CHARS = 300
AUDIT_MAX_ITEMS = 20

NEWS_BASE_QUERY = "síndrome respiratória aguda grave SRAG"
NEWS_COUNTRY_NAME = "Brasil"
NEWS_QUERY_MAX_CHARS = 200
NEWS_TITLE_MAX_CHARS = 200
NEWS_SNIPPET_MAX_CHARS = 500


class Settings(BaseSettings):
    """All tunable values of the project. Secrets are never printed (SecretStr)."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    anthropic_api_key: SecretStr = SecretStr("")
    tavily_api_key: SecretStr = SecretStr("")

    llm_model: str = "claude-haiku-5-5"
    # Claude Haiku 5.5 rejects non-default sampling parameters, so there is no temperature
    # setting. Effort controls how much the model reasons (and how many tokens it bills).
    llm_effort: Literal["low", "medium", "high"] = "low"
    llm_max_tokens: int = Field(default=4000, gt=0)  # includes the model's reasoning tokens
    llm_timeout_seconds: int = Field(default=60, gt=0)
    llm_price_input_per_mtok: float = Field(default=0.10, ge=0)
    llm_price_output_per_mtok: float = Field(default=0.50, ge=0)

    agent_max_iterations: int = Field(default=8, gt=0)
    run_timeout_seconds: int = Field(default=180, gt=0)
    max_cost_usd_per_run: float = Field(default=0.10, gt=0)

    news_max_results: int = Field(default=10, gt=0)
    news_max_items: int = Field(default=5, gt=0)
    # Each search spends one Tavily credit: one search plus at most one refinement by default.
    news_max_searches: int = Field(default=2, gt=0)
    news_days: int = Field(default=30, gt=0)
    news_timeout_seconds: int = Field(default=20, gt=0)

    metric_window_days: int = Field(default=30, gt=0)
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
