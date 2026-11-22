import json
from pathlib import Path

import pytest

from srag import service
from srag.config import MEDICAL_DISCLAIMER, Settings
from srag.data.repository import CaseRepository
from srag.guardrails.input import InvalidRequestError
from srag.metrics.snapshot import compute_metrics
from srag.report.pdf import PdfGenerationError
from tests.agent.fakes import (
    FakeChatModel,
    FakeSearcher,
    news_result,
    text_message,
    tool_calls_message,
)
from tests.agent.helpers import synthetic_cases, valid_report_text

NEWS_URL = "https://agencia.fiocruz.br/infogripe-1"
ALL_TOOLS = tool_calls_message(
    ("get_metrics", {}), ("get_case_series", {}), ("search_news", {"query": "SRAG casos"})
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    parquet = tmp_path / "srag.parquet"
    synthetic_cases().to_parquet(parquet, index=False)
    return Settings(
        _env_file=None,
        anthropic_api_key="fake",
        tavily_api_key="fake",
        data_processed_path=parquet,
        reports_dir=tmp_path / "reports",
    )


@pytest.fixture
def writer_text(settings: Settings) -> str:
    with CaseRepository(settings.data_processed_path) as repository:
        snapshot = compute_metrics(repository, "SP", settings)
    return valid_report_text(snapshot, NEWS_URL)


def generate(settings, script, batches=(), **options):
    return service.generate_report(
        "SP",
        settings=settings,
        llm=FakeChatModel(script=list(script)),
        searcher=FakeSearcher(list(batches)),
        **options,
    )


def test_generates_html_audit_and_manifest(settings, writer_text):
    result = generate(
        settings, [ALL_TOOLS, text_message(writer_text)], [[news_result(1)]], with_pdf=False
    )

    assert result.status == "completed"
    assert result.pdf_path is None
    html = result.html_path.read_text(encoding="utf-8")
    assert "Relatório de SRAG: São Paulo (SP)" in html
    assert NEWS_URL in html
    assert MEDICAL_DISCLAIMER in html
    assert result.audit_path.exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == result.run_id
    assert manifest["status"] == "completed"
    assert manifest["scope"] == "SP"
    assert manifest["data_max_date"] == "2026-11-15"
    assert result.run_dir.parent == settings.reports_dir


def test_pdf_is_generated_next_to_the_html(settings, writer_text, monkeypatch):
    def fake_pdf(html_path: Path, pdf_path: Path) -> Path:
        pdf_path.write_bytes(b"%PDF-fake")
        return pdf_path

    monkeypatch.setattr(service, "html_to_pdf", fake_pdf)

    result = generate(settings, [ALL_TOOLS, text_message(writer_text)], [[news_result(1)]])

    assert result.pdf_path == result.html_path.with_name("report.pdf")
    assert result.pdf_path.read_bytes() == b"%PDF-fake"


def test_a_pdf_failure_keeps_the_html_report_and_is_audited(settings, writer_text, monkeypatch):
    def broken_pdf(html_path: Path, pdf_path: Path) -> Path:
        raise PdfGenerationError("PDF generation failed: Error")

    monkeypatch.setattr(service, "html_to_pdf", broken_pdf)

    result = generate(settings, [ALL_TOOLS, text_message(writer_text)], [[news_result(1)]])

    assert result.pdf_path is None
    assert result.html_path.exists()
    events = [json.loads(line) for line in result.audit_path.read_text("utf-8").splitlines()]
    assert any(e["event_type"] == "error" and e["node"] == "pdf" for e in events)


def test_a_stopped_run_still_produces_a_report(settings):
    tight = settings.model_copy(update={"max_cost_usd_per_run": 0.0000001})

    result = generate(tight, [ALL_TOOLS], with_pdf=False)

    assert result.status == "stopped"
    assert result.stop_reason == "max_cost_exceeded"
    html = result.html_path.read_text(encoding="utf-8")
    assert "O texto explicativo automático não está disponível" in html


def test_an_invalid_uf_is_rejected_before_any_run_folder_is_created(settings):
    with pytest.raises(InvalidRequestError):
        service.generate_report("XX", settings=settings)

    assert not settings.reports_dir.exists()


def test_a_failure_is_audited_and_the_manifest_records_the_error(settings):
    settings.data_processed_path.unlink()

    with pytest.raises(Exception):  # noqa: B017 - any data loading error must be re-raised
        generate(settings, [])

    run_dir = next(settings.reports_dir.iterdir())
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "error"
    assert manifest["data_file_sha256"] is None
    assert '"event_type": "error"' in (run_dir / "audit.jsonl").read_text(encoding="utf-8")
