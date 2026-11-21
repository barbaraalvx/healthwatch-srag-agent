"""Pure metric functions. Formulas and limitations are documented in docs/METRICS.md."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from srag.data import schema

CASE_GROWTH_RATE = "case_growth_rate"
MORTALITY_RATE = "mortality_rate"
ICU_ADMISSION_RATE = "icu_admission_rate"
COVID_VACCINATION_RATE = "covid_vaccination_rate"
FLU_VACCINATION_RATE = "flu_vaccination_rate"

PERCENT = 100

NOTE_GROWTH = (
    "Compara a janela atual com a janela anterior de mesmo tamanho. Os dias mais recentes "
    "ficam de fora por causa do atraso de notificação."
)
NOTE_MORTALITY = (
    "Letalidade entre os casos com desfecho conhecido. Casos ainda em aberto não entram na conta."
)
NOTE_ICU = (
    "Proxy: proporção de internações por SRAG que necessitaram de UTI. "
    "Não é a ocupação de leitos, pois a base não traz a capacidade de UTI."
)
NOTE_COVID_VACCINE = (
    "Proxy: proporção de casos de SRAG vacinados contra COVID-19. "
    "Não é a cobertura vacinal da população."
)
NOTE_FLU_VACCINE = (
    "Proxy secundário: proporção de casos de SRAG vacinados contra gripe. "
    "Não é a cobertura vacinal da população."
)


@dataclass(frozen=True)
class Window:
    start: date
    end: date


@dataclass(frozen=True)
class MetricResult:
    name: str
    value: float | None
    numerator: int
    denominator: int
    completeness: float
    window_start: date
    window_end: date
    unstable: bool
    note: str | None


def build_windows(reference_date: date, lag_days: int, window_days: int) -> tuple[Window, Window]:
    """Return (current, previous) windows, skipping the last lag_days of recent notifications."""
    current_end = reference_date - timedelta(days=lag_days)
    current = _window_ending_at(current_end, window_days)
    previous = _window_ending_at(current.start - timedelta(days=1), window_days)
    return current, previous


def _window_ending_at(end: date, window_days: int) -> Window:
    return Window(start=end - timedelta(days=window_days - 1), end=end)


def case_growth_rate(
    current_cases: int, previous_cases: int, window: Window, min_denominator: int
) -> MetricResult:
    """Percent change in cases versus the previous window; undefined when it had no cases."""
    value = None
    if previous_cases > 0:
        value = (current_cases - previous_cases) / previous_cases * PERCENT
    return MetricResult(
        name=CASE_GROWTH_RATE,
        value=value,
        numerator=current_cases,
        denominator=previous_cases,
        completeness=1.0,
        window_start=window.start,
        window_end=window.end,
        unstable=previous_cases < min_denominator,
        note=NOTE_GROWTH,
    )


def mortality_rate(
    outcome_counts: Mapping[int, int], total_cases: int, window: Window, min_denominator: int
) -> MetricResult:
    """Deaths by SRAG among cases with a closed outcome."""
    return _rate_among_known(
        MORTALITY_RATE, outcome_counts, schema.OUTCOME, total_cases, window, min_denominator,
        positive_code=schema.OUTCOME_DEATH_BY_SRAG, note=NOTE_MORTALITY,
    )  # fmt: skip


def icu_admission_rate(
    icu_counts: Mapping[int, int], total_cases: int, window: Window, min_denominator: int
) -> MetricResult:
    """Share of cases with known ICU status that were admitted to an ICU (proxy)."""
    return _rate_among_known(
        ICU_ADMISSION_RATE, icu_counts, schema.ICU, total_cases, window, min_denominator,
        positive_code=schema.CODE_YES, note=NOTE_ICU,
    )  # fmt: skip


def covid_vaccination_rate(
    vaccine_counts: Mapping[int, int], total_cases: int, window: Window, min_denominator: int
) -> MetricResult:
    """Share of cases with known status that had a COVID-19 vaccine (proxy)."""
    return _rate_among_known(
        COVID_VACCINATION_RATE, vaccine_counts, schema.COVID_VACCINE, total_cases, window,
        min_denominator, positive_code=schema.CODE_YES, note=NOTE_COVID_VACCINE,
    )  # fmt: skip


def flu_vaccination_rate(
    vaccine_counts: Mapping[int, int], total_cases: int, window: Window, min_denominator: int
) -> MetricResult:
    """Share of cases with known status that had a flu vaccine (secondary proxy)."""
    return _rate_among_known(
        FLU_VACCINATION_RATE, vaccine_counts, schema.FLU_VACCINE, total_cases, window,
        min_denominator, positive_code=schema.CODE_YES, note=NOTE_FLU_VACCINE,
    )  # fmt: skip


def _rate_among_known(
    name: str,
    counts: Mapping[int, int],
    column: str,
    total_cases: int,
    window: Window,
    min_denominator: int,
    positive_code: int,
    note: str,
) -> MetricResult:
    denominator = sum(counts.get(code, 0) for code in schema.VALID_CODES[column])
    numerator = counts.get(positive_code, 0)
    return MetricResult(
        name=name,
        value=numerator / denominator * PERCENT if denominator else None,
        numerator=numerator,
        denominator=denominator,
        completeness=denominator / total_cases if total_cases else 0.0,
        window_start=window.start,
        window_end=window.end,
        unstable=denominator < min_denominator,
        note=note,
    )
