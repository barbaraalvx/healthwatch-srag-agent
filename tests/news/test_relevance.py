from datetime import date

import pytest

from srag.news.models import NewsItem
from srag.news.relevance import filter_relevant, is_relevant
from srag.text import normalize


def news(title: str, snippet: str = "Texto.", source: str = "g1.globo.com") -> NewsItem:
    return NewsItem(title, f"https://{source}/x", source, date(2026, 11, 20), snippet)


@pytest.mark.parametrize(
    "title",
    [
        "Family's anger after grandfather's botched burial",
        "Flávio Bolsonaro lands in Miami after defeat in Brazil's presidential election",
        "Kennedys sue to block Trump's arch",
    ],
)
def test_off_topic_news_from_the_real_test_run_is_rejected(title):
    assert not is_relevant(news(title, source="bbc.com"), None)


def test_international_news_about_respiratory_disease_elsewhere_is_rejected():
    item = news(
        "Reported bird flu case being investigated",
        "A reported case of bird flu at a poultry farm in County Tyrone.",
        source="bbc.com",
    )

    assert not is_relevant(item, None)


def test_international_news_that_mentions_brazil_is_kept():
    item = news("Brazil reports rise in severe respiratory cases", source="bbc.com")

    assert is_relevant(item, None)


def test_international_news_for_a_state_can_mention_the_state_instead():
    item = news("Surto de gripe em São Paulo preocupa a OMS", source="who.int")

    assert is_relevant(item, "SP")
    assert not is_relevant(item, "RJ")


@pytest.mark.parametrize(
    "title",
    [
        "Casos de SRAG sobem em São Paulo",
        "Síndrome Respiratória Aguda Grave: Fiocruz alerta para aumento",
        "Aumentam as internações por influenza no Sul",
        "Covid-19 volta a crescer, mostra boletim InfoGripe",
        "Vírus sincicial respiratório lota enfermarias pediátricas",
        "InfoGripe: cinco estados têm nível de alerta",
        "Vigilância Sentinela de Síndrome Gripal",
    ],
)
def test_national_news_about_the_topic_is_kept(title):
    assert is_relevant(news(title), None)


def test_topic_can_be_found_in_the_snippet():
    assert is_relevant(news("Boletim semanal", "Cresce o número de casos de SRAG."), None)


def test_word_fragments_do_not_count_as_the_topic():
    assert not is_relevant(news("Fluxo de caixa cresce", "O fluido escorreu."), None)


def test_normalize_removes_accents_and_case():
    assert normalize("Síndrome RESPIRATÓRIA") == "sindrome respiratoria"


def test_filter_relevant_keeps_order_and_drops_the_rest():
    relevant = news("SRAG em alta")
    other = news("Futebol: resultado da rodada")

    assert filter_relevant([other, relevant], None) == (relevant,)
