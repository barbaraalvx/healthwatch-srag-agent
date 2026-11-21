from datetime import date

import pytest

from srag.config import MEDICAL_DISCLAIMER, Settings
from srag.guardrails.output import (
    OutputContext,
    check_citations,
    check_disclaimer,
    check_numbers,
    check_personal_data,
    check_sections,
    extract_numbers,
    structural_numbers,
    validate_output,
)
from srag.metrics.calculations import MetricResult
from srag.news.models import NewsItem

WINDOW_START, WINDOW_END = date(2026, 10, 10), date(2026, 11, 8)
NEWS_URL = "https://agencia.fiocruz.br/infogripe-cinco-estados"


def metric(name: str, value, numerator: int, denominator: int, completeness: float) -> MetricResult:
    return MetricResult(
        name, value, numerator, denominator, completeness, WINDOW_START, WINDOW_END, False, None
    )


METRICS = (
    metric("case_growth_rate", -14.434, 14233, 16634, 1.0),
    metric("mortality_rate", 4.489, 337, 7507, 0.527),
    metric("icu_admission_rate", 29.279, 3592, 12268, 0.862),
    metric("flu_vaccination_rate", None, 0, 0, 0.0),
)
NEWS = (
    NewsItem(
        "InfoGripe: cinco estados têm SRAG em nível de alerta",
        NEWS_URL,
        "agencia.fiocruz.br",
        None,
        "Boletim mostra que 5 das 27 unidades da Federação estão em alerta.",
    ),
)
CONTEXT = OutputContext(METRICS, NEWS, date(2026, 11, 15), (30, 7, 30, 12, 30))

VALID_TEXT = f"""## Resumo executivo
Os casos de SRAG caíram 14,4% frente à janela anterior (14.233 contra 16.634 casos).
A letalidade entre os casos encerrados foi de 4,5%, com 52,7% dos desfechos conhecidos.

## Análise do cenário
A Fiocruz informa que 5 das 27 unidades da Federação estão em alerta ([1]({NEWS_URL})).
Dados até 15/11/2026, janela de 30 dias, sem os últimos 7 dias. COVID-19 e H1N1 circulam.

{MEDICAL_DISCLAIMER}
"""


def text_with(extra: str) -> str:
    return VALID_TEXT + "\n" + extra


def test_a_correct_text_passes_every_check():
    result = validate_output(VALID_TEXT, CONTEXT)

    assert result.passed
    assert result.errors == ()


# --- numbers -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "A mortalidade foi de 4,5%.",  # 4.489 rounded
        "A mortalidade foi de 4,4%.",  # inside the 0.1 tolerance
        "Queda de 14,4%.",  # growth is -14.434: the sign is written as a word
        "Variação de -14,4%.",
        "Foram 14.233 casos e 14233 notificações.",
        "A completude foi de 52,7%.",
        "Foram 337 óbitos entre 7.507 desfechos.",
        "A janela é de 30 dias, com 7 dias de atraso, em 12 meses.",
        "Dados de 2026 e 2025.",
    ],
)
def test_numbers_that_match_computed_values_are_accepted(sentence):
    assert check_numbers(sentence, CONTEXT) == []


@pytest.mark.parametrize(
    "sentence",
    [
        "A mortalidade foi de 7,2%.",  # invented
        "A mortalidade foi de 4,6%.",  # 0.111 away: outside the tolerance
        "Foram 14.234 casos.",  # counts must match exactly
        "Foram 45 dias de atraso.",
        "Dados de 2024.",
        "A vacinação foi de 40,3%.",  # that metric is undefined, no value exists
    ],
)
def test_numbers_that_match_nothing_are_rejected(sentence):
    errors = check_numbers(sentence, CONTEXT)

    assert len(errors) == 1
    assert "does not match any computed value" in errors[0]


def test_the_rejected_number_is_named_in_the_error():
    (error,) = check_numbers("A mortalidade foi de 7,2%.", CONTEXT)

    assert "'7,2'" in error


def test_numbers_from_the_retrieved_news_are_accepted_only_exactly():
    assert check_numbers("Cinco estados: 5 de 27 UFs.", CONTEXT) == []
    assert len(check_numbers("Seis estados: 6 de 27 UFs.", CONTEXT)) == 1


def test_dates_codes_urls_list_markers_and_citation_numbers_are_not_checked():
    text = (
        "1. Item numerado.\n2. Outro item.\n"
        "Veja [3] e https://example.org/relatorio-98765/2026.\n"
        "Datas: 15/11, 15/11/2026, 2026-11-15. Vírus: COVID-19, H1N1, SE43."
    )

    assert check_numbers(text, CONTEXT) == []


def test_english_decimal_format_is_not_accepted():
    numbers = [token for token, _ in extract_numbers("A taxa foi de 4.5%.")]

    assert numbers == ["4", "5"]


def test_extract_numbers_reads_pt_br_formats():
    found = dict(extract_numbers("1.234,5 e 4,5 e 12 e 10.000"))

    assert found == {"1.234,5": 1234.5, "4,5": 4.5, "12": 12.0, "10.000": 10000.0}


def test_structural_numbers_come_from_the_settings():
    assert structural_numbers(Settings(_env_file=None)) == (30, 7, 30, 12, 30)


# --- citations ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"Fonte: {NEWS_URL}",
        f"Fonte: {NEWS_URL}.",
        f"Fonte: ({NEWS_URL}), segundo a Fiocruz.",
        f"Fonte: {NEWS_URL}/",
        f"[Fiocruz]({NEWS_URL})",
        "Sem links.",
    ],
)
def test_urls_from_the_retrieved_news_are_accepted(text):
    assert check_citations(text, NEWS) == []


@pytest.mark.parametrize(
    "url",
    [
        "https://invented.example.com/noticia",
        "https://agencia.fiocruz.br/outra-pagina",
        f"{NEWS_URL}-diferente",
    ],
)
def test_urls_that_were_not_retrieved_are_rejected(url):
    errors = check_citations(f"Fonte: {url}", NEWS)

    assert errors == [f"URL is not among the retrieved sources: {url}"]


def test_any_url_is_rejected_when_no_news_was_retrieved():
    assert len(check_citations(f"Fonte: {NEWS_URL}", ())) == 1
    assert check_citations("Nenhuma fonte.", ()) == []


# --- sections and disclaimer -------------------------------------------------------------


def test_missing_required_section_is_reported():
    text = VALID_TEXT.replace("## Análise do cenário", "Análise do cenário")

    assert check_sections(text) == ["Required section is missing: Análise do cenário"]


def test_section_names_ignore_case_accents_and_heading_level():
    text = "### RESUMO EXECUTIVO\ntexto\n## analise do cenario\ntexto"

    assert check_sections(text) == []


def test_text_without_any_section_reports_all_of_them():
    assert len(check_sections("Apenas um parágrafo.")) == 2


def test_disclaimer_is_required():
    assert check_disclaimer(VALID_TEXT) == []
    assert check_disclaimer("Texto sem aviso.") == ["The medical disclaimer is missing"]


def test_disclaimer_may_be_wrapped_across_lines():
    wrapped = "\n".join(MEDICAL_DISCLAIMER.split(" "))

    assert check_disclaimer(f"Texto.\n{wrapped}") == []


# --- personal data -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("Paciente 123.456.789-09 internado.", "CPF"),
        ("Documento 12345678909.", "CPF"),
        ("Contato: maria.silva@exemplo.com.br", "e-mail"),
        ("Ligue (11) 98765-4321.", "phone number"),
        ("Ligue +55 11 98765-4321.", "phone number"),
    ],
)
def test_personal_data_patterns_are_detected(text, label):
    assert check_personal_data(text) == [f"Possible personal data ({label}) found in the text"]


@pytest.mark.parametrize(
    "text", ["Foram 14.233 casos em 2025-2026.", "Entre 10/10 e 08/11, 52,7% e 4.489 casos."]
)
def test_numbers_and_year_ranges_are_not_mistaken_for_personal_data(text):
    assert check_personal_data(text) == []


# --- full validation ---------------------------------------------------------------------


def test_validation_reports_every_problem_at_once():
    bad = "Mortalidade de 7,2%. https://invented.example.com/x. Contato a@b.com"

    result = validate_output(bad, CONTEXT)

    assert not result.passed
    assert len(result.errors) == 6
    assert any("7,2" in error for error in result.errors)
    assert any("invented.example.com" in error for error in result.errors)
    assert any("Required section" in error for error in result.errors)
    assert any("disclaimer" in error for error in result.errors)
    assert any("personal data" in error for error in result.errors)


def test_a_valid_text_with_an_invented_extra_sentence_fails():
    result = validate_output(text_with("A letalidade chegou a 9,9%."), CONTEXT)

    assert not result.passed
    assert len(result.errors) == 1
