from pathlib import Path
from types import SimpleNamespace

import pytest

from srag import __main__ as cli
from srag import service
from srag.config import Settings


def fake_result(status="completed", stop_reason=None, pdf=Path("report.pdf")):
    return SimpleNamespace(
        run_id="run-1",
        status=status,
        stop_reason=stop_reason,
        html_path=Path("report.html"),
        pdf_path=pdf,
        audit_path=Path("audit.jsonl"),
        manifest_path=Path("manifest.json"),
    )


@pytest.fixture
def calls(monkeypatch) -> list[dict]:
    recorded: list[dict] = []

    def fake_generate(uf, *, settings, with_pdf):
        recorded.append({"uf": uf, "settings": settings, "with_pdf": with_pdf})
        return fake_result()

    monkeypatch.setattr(service, "generate_report", fake_generate)
    return recorded


def test_default_run_is_brazil_with_pdf_and_prints_the_files(calls, capsys):
    code = cli.main([])

    assert code == cli.EXIT_OK
    assert calls[0]["uf"] is None
    assert calls[0]["with_pdf"] is True
    output = capsys.readouterr().out
    assert "Run run-1: completed" in output
    for label in ("HTML:", "PDF:", "Audit:", "Manifest:"):
        assert label in output


def test_uf_and_no_pdf_options_are_passed_on(calls):
    cli.main(["--uf", "SP", "--no-pdf"])

    assert calls[0]["uf"] == "SP"
    assert calls[0]["with_pdf"] is False


def test_output_dir_replaces_the_reports_folder(calls, tmp_path):
    cli.main(["--output-dir", str(tmp_path / "out")])

    assert calls[0]["settings"].reports_dir == (tmp_path / "out").resolve()


def test_a_stopped_run_explains_that_there_is_no_automatic_text(monkeypatch, capsys):
    stopped = fake_result("stopped", "max_cost_exceeded", pdf=None)
    monkeypatch.setattr(service, "generate_report", lambda *a, **k: stopped)

    assert cli.main([]) == cli.EXIT_OK

    output = capsys.readouterr().out
    assert "max_cost_exceeded" in output
    assert "not generated" in output


def test_an_invalid_uf_gives_a_clear_message_and_exit_code_2(capsys):
    code = cli.main(["--uf", "XX"])

    assert code == cli.EXIT_INVALID_REQUEST
    error = capsys.readouterr().err
    assert error.startswith("error: Invalid request")
    assert "Traceback" not in error


def test_missing_data_is_reported_without_a_stack_trace(monkeypatch, tmp_path, capsys):
    settings = Settings(_env_file=None, data_processed_path=tmp_path / "missing.parquet")
    monkeypatch.setattr(cli, "get_settings", lambda: settings)

    code = cli.main([])

    assert code == cli.EXIT_FAILURE
    error = capsys.readouterr().err
    assert "Processed data not found" in error
    assert "Traceback" not in error


def test_an_unexpected_failure_is_one_line_and_exit_code_1(monkeypatch, capsys):
    def broken(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(service, "generate_report", broken)

    code = cli.main([])

    assert code == cli.EXIT_FAILURE
    error = capsys.readouterr().err
    assert "RuntimeError" in error
    assert "secret internal detail" not in error
    assert "Traceback" not in error
