from dataclasses import replace
from datetime import date

from srag.agent.writer_input import UNSTABLE_FLAG, build_writer_input, describe_metric
from srag.formatting import METRIC_LABELS
from srag.metrics.calculations import (
    CASE_GROWTH_RATE,
    FLU_VACCINATION_RATE,
    MORTALITY_RATE,
    MetricResult,
    Window,
)

WINDOW = Window(date(2026, 10, 10), date(2026, 11, 8))


def result(name: str, value, numerator, denominator, completeness=1.0, unstable=False, note=None):
    return MetricResult(
        name, value, numerator, denominator, completeness, WINDOW.start, WINDOW.end, unstable, note
    )


def test_growth_line_shows_the_signed_value_and_both_case_counts():
    line = describe_metric(result(CASE_GROWTH_RATE, -14.434, 14233, 16634))

    assert "-14,4%" in line
    assert "14.233 casos na janela atual contra 16.634 na anterior" in line


def test_rate_line_shows_value_basis_and_completeness():
    line = describe_metric(result(MORTALITY_RATE, 4.489, 337, 7507, 0.527))

    assert "4,5% (337 de 7.507 casos com informação conhecida; completude de 52,7%)" in line


def test_undefined_values_are_stated_instead_of_a_number():
    growth = describe_metric(result(CASE_GROWTH_RATE, None, 40, 0))
    rate = describe_metric(result(FLU_VACCINATION_RATE, None, 0, 0, 0.0))

    assert "indefinida (a janela anterior não teve casos)" in growth
    assert "indefinida (nenhum caso com informação conhecida)" in rate
    assert "None" not in growth + rate


def test_unstable_metrics_are_flagged_and_notes_are_included():
    line = describe_metric(result(MORTALITY_RATE, 10.0, 1, 10, 0.5, unstable=True, note="Nota X."))

    assert UNSTABLE_FLAG in line
    assert line.endswith("Nota: Nota X.")


def test_writer_input_has_scope_dates_windows_metrics_and_news(snapshot):
    text = build_writer_input(snapshot, "BLOCO DE NOTICIAS")

    assert "Escopo: São Paulo (SP)" in text
    assert "Data de referência dos dados: 15/11/2026" in text
    assert "Janela atual: 10/10/2026 a 08/11/2026 (30 dias, sem os últimos 7 dias" in text
    assert "Janela anterior: 10/09/2026 a 09/10/2026" in text
    assert text.count("\n- ") == len(snapshot.metrics)
    assert text.endswith("Notícias:\nBLOCO DE NOTICIAS")


def test_every_computed_metric_has_a_label_for_the_writer(snapshot):
    assert {metric.name for metric in snapshot.metrics} <= set(METRIC_LABELS)


def test_writer_input_for_brazil(snapshot):
    text = build_writer_input(replace(snapshot, uf=None), "x")

    assert "Escopo: Brasil" in text
