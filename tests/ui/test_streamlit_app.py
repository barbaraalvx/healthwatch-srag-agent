import pytest
from streamlit.testing.v1 import AppTest

from srag import service
from srag.config import VALID_UFS
from srag.ui import streamlit_app
from tests.agent.fakes import (
    FakeChatModel,
    FakeSearcher,
    news_result,
    text_message,
    tool_calls_message,
)

ALL_TOOLS = tool_calls_message(
    ("get_metrics", {}), ("get_case_series", {}), ("search_news", {"query": "SRAG casos"})
)
APP_TIMEOUT_SECONDS = 60


@pytest.fixture
def app() -> AppTest:
    return AppTest.from_file(streamlit_app.__file__, default_timeout=APP_TIMEOUT_SECONDS)


@pytest.fixture
def fake_service(monkeypatch, service_settings, writer_text):
    """The real service with a fake model and searcher, and without the PDF (faster)."""
    original = service.generate_report

    def generate(uf):
        return original(
            uf,
            settings=service_settings,
            with_pdf=False,
            llm=FakeChatModel(script=[ALL_TOOLS, text_message(writer_text)]),
            searcher=FakeSearcher([[news_result(1)]]),
        )

    monkeypatch.setattr(service, "generate_report", generate)


def test_scope_selector_offers_brazil_and_every_state(app):
    app.run()

    options = app.selectbox[0].options
    assert options[0] == "Brasil"
    assert len(options) == 1 + len(VALID_UFS)
    assert "São Paulo (SP)" in options


def test_nothing_is_generated_until_the_button_is_clicked(app, fake_service):
    app.run()

    assert not app.metric
    assert not app.exception


def test_generating_shows_metrics_text_sources_and_the_audit_panel(app, fake_service):
    app.run()
    app.selectbox[0].select("São Paulo (SP)")
    app.button[0].click().run()

    assert not app.exception
    assert len(app.metric) == 5
    assert app.metric[0].label == "Taxa de aumento de casos"
    assert "São Paulo (SP)" in app.subheader[0].value
    assert [expander.label for expander in app.expander] == ["Auditoria desta execução"]
    assert len(app.dataframe) == 1
    markdown = " ".join(element.value for element in app.markdown)
    assert "Resumo executivo" in markdown
    assert "Análise do cenário" in markdown
    assert "infogripe-1" in markdown


def test_a_missing_data_file_shows_a_friendly_error(app, monkeypatch):
    def not_prepared(uf):
        raise service.DataNotPreparedError("missing")

    monkeypatch.setattr(service, "generate_report", not_prepared)
    app.run()
    app.button[0].click().run()

    assert "dados ainda não foram preparados" in app.error[0].value
    assert not app.exception


def test_an_unexpected_failure_never_shows_a_stack_trace(app, monkeypatch):
    def broken(uf):
        raise RuntimeError("internal detail")

    monkeypatch.setattr(service, "generate_report", broken)
    app.run()
    app.button[0].click().run()

    assert "RuntimeError" in app.error[0].value
    assert "internal detail" not in app.error[0].value
    assert not app.exception
