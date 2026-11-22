"""pt-BR formatting of numbers, dates and metric names, shared by the agent and the report."""

from datetime import date

from srag.config import UF_NAMES
from srag.metrics.calculations import (
    CASE_GROWTH_RATE,
    COVID_VACCINATION_RATE,
    FLU_VACCINATION_RATE,
    ICU_ADMISSION_RATE,
    MORTALITY_RATE,
)

BRAZIL_NAME = "Brasil"

METRIC_LABELS: dict[str, str] = {
    CASE_GROWTH_RATE: "Variação do número de casos (janela atual contra janela anterior)",
    MORTALITY_RATE: "Taxa de mortalidade (óbitos por SRAG entre casos com desfecho conhecido)",
    ICU_ADMISSION_RATE: "Proporção de internações por SRAG que necessitaram de UTI (proxy)",
    COVID_VACCINATION_RATE: "Proporção de casos de SRAG vacinados contra COVID-19 (proxy)",
    FLU_VACCINATION_RATE: "Proporção de casos de SRAG vacinados contra gripe (proxy)",
}


def format_percent(value: float) -> str:
    """One decimal place with a comma: 4.489 -> '4,5%'. Never prints '-0,0%'."""
    rounded = round(value, 1)
    return f"{rounded + 0.0:.1f}".replace(".", ",") + "%"


def format_count(value: int) -> str:
    """Thousands separated by dots: 14233 -> '14.233'."""
    return f"{value:,}".replace(",", ".")


def format_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def scope_name(uf: str | None) -> str:
    """'Brasil' or 'São Paulo (SP)'."""
    return BRAZIL_NAME if uf is None else f"{UF_NAMES[uf]} ({uf})"
