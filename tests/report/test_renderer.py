from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from srag.agent.fallback import fallback_text
from srag.agent.graph import AgentResult
from srag.config import MEDICAL_DISCLAIMER, REQUIRED_REPORT_SECTIONS
from srag.news.models import NewsItem
from srag.report.context import AI_TEXT_UNAVAILABLE, RunDetails, build_report_context
from srag.report.renderer import render_report
from tests.agent.helpers import valid_report_text

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake"
NEWS = NewsItem(
    title="InfoGripe mostra alta",
    url="https://agencia.fiocruz.br/infogripe-1",
    source="agencia.fiocruz.br",
    published_at=None,
    snippet="texto",
)
RUN = RunDetails(
    run_id="11111111-2222-3333-4444-555555555555",
    generated_at=datetime(2026, 11, 22, 10, 30, tzinfo=UTC),
    model="claude-haiku-5-5",
    effort="low",
    prompt_versions={"orchestrator": "orchestrator_v1", "writer": "writer_v1"},
)


@pytest.fixture
def make_result(tmp_path: Path, snapshot):
    daily, monthly = tmp_path / "daily.png", tmp_path / "monthly.png"
    daily.write_bytes(PNG_BYTES)
    monthly.write_bytes(PNG_BYTES)

    def build(text=None, status="completed", news=(NEWS,), stop_reason=None) -> AgentResult:
        text = text or f"{valid_report_text(snapshot, NEWS.url)}\n\n{MEDICAL_DISCLAIMER}\n"
        return AgentResult(
            status=status,
            report_text=text,
            snapshot=snapshot,
            daily_chart=daily,
            monthly_chart=monthly,
            news_items=news,
            stop_reason=stop_reason,
            validation_errors=(),
            writer_attempts=1,
        )

    return build


def render(result) -> str:
    return render_report(build_report_context(result, RUN))


def test_report_has_every_required_section(make_result):
    html = render(make_result())

    for title in (*REQUIRED_REPORT_SECTIONS, "Métricas", "Gráficos"):
        assert f"<h2>{title}</h2>" in html
    assert "<h2>Limitações e notas metodológicas</h2>" in html
    assert "<h2>Fontes</h2>" in html


def test_header_and_footer_show_scope_dates_and_run_details(make_result):
    html = render(make_result())

    assert "Relatório de SRAG: São Paulo (SP)" in html
    assert "Dados até 15/11/2026" in html
    assert RUN.run_id in html
    assert "22/11/2026 10:30 UTC" in html
    assert "claude-haiku-5-5" in html
    assert "orchestrator orchestrator_v1, writer writer_v1" in html


def test_there_is_one_card_per_metric_with_formatted_values(make_result, snapshot):
    context = build_report_context(make_result(), RUN)

    assert len(context.cards) == len(snapshot.metrics) == 5
    growth = context.cards[0]
    assert growth.title == "Taxa de aumento de casos"
    assert growth.value.endswith("%") and "," in growth.value
    assert growth.completeness is None
    assert context.cards[1].completeness is not None


def test_charts_are_embedded_as_base64_images(make_result):
    html = render(make_result())

    assert html.count("data:image/png;base64,") == 2


def test_disclaimer_appears_once_in_the_footer_only(make_result):
    html = render(make_result())

    assert html.count(MEDICAL_DISCLAIMER) == 1
    assert html.rindex(MEDICAL_DISCLAIMER) > html.index("<footer>")


def test_sources_list_the_retrieved_news_with_links(make_result):
    html = render(make_result())

    assert f'<a href="{NEWS.url}">{NEWS.title}</a>' in html
    assert "sem data de publicação" in html


def test_report_says_when_there_is_no_news(make_result):
    html = render(make_result(news=()))

    assert "Nenhuma notícia confiável foi encontrada para esta execução." in html


def test_fallback_report_shows_a_notice(make_result):
    result = make_result(text=fallback_text("max_cost_exceeded"), status="stopped")

    html = render(result)

    assert AI_TEXT_UNAVAILABLE in html
    assert "<h2>Resumo executivo</h2>" in html


def test_completed_report_has_no_notice(make_result):
    assert AI_TEXT_UNAVAILABLE not in render(make_result())


def test_text_from_the_model_cannot_inject_html(make_result):
    text = "## Resumo executivo\n<script>x()</script>\n\n## Análise do cenário\nok\n"

    html = render(make_result(text=text))

    assert "<script>x()</script>" not in html


def test_news_titles_are_escaped(make_result):
    evil = NewsItem("<img src=x onerror=y>", NEWS.url, NEWS.source, date(2026, 11, 1), "t")

    html = render(make_result(news=(evil,)))

    assert "<img src=x" not in html
    assert "01/11/2026" in html


def test_four_primary_cards_and_the_secondary_flu_metric(make_result):
    context = build_report_context(make_result(), RUN)

    assert [card.primary for card in context.cards] == [True, True, True, True, False]
    assert context.cards[-1].title == "Taxa de vacinação gripe (proxy)"


def test_case_growth_card_shows_the_direction_of_the_change(make_result):
    context = build_report_context(make_result(), RUN)

    assert context.cards[0].trend == "down"
    assert all(card.trend is None for card in context.cards[1:])
    assert "trend-down" in render(make_result())


def test_header_shows_the_analysis_window(make_result):
    html = render(make_result())

    assert "10/10/2026 a 08/11/2026" in html
    assert "Janela de análise" in html


def test_metrics_table_has_a_row_for_every_metric(make_result):
    html = render(make_result())

    assert html.count('<span class="dot dot-') == 5
    assert "Estável" in html


def test_quick_links_point_to_the_files_of_the_run(make_result):
    html = render(make_result())

    for target in ("report.pdf", "audit.jsonl", "manifest.json"):
        assert f'href="{target}"' in html


def test_cards_use_the_metric_names_of_the_brief(make_result):
    titles = [card.title for card in build_report_context(make_result(), RUN).cards]

    assert titles[:3] == [
        "Taxa de aumento de casos",
        "Taxa de mortalidade",
        "Taxa de ocupação de UTI (proxy)",
    ]
    assert titles[3].startswith("Taxa de vacinação")


def test_proxy_cards_carry_their_limitation_note(make_result):
    html = render(make_result())

    assert "Não é a ocupação de leitos" in html
    assert "Não é a cobertura vacinal da população" in html
