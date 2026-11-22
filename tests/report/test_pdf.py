from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from srag.report.pdf import PdfGenerationError, html_to_pdf


def chromium_is_installed() -> bool:
    try:
        with sync_playwright() as playwright:
            return Path(playwright.chromium.executable_path).exists()
    except Exception:  # noqa: BLE001 - any failure here just means "skip the browser tests"
        return False


needs_chromium = pytest.mark.skipif(not chromium_is_installed(), reason="Chromium is not installed")


@needs_chromium
def test_html_is_converted_to_a_pdf_file(tmp_path: Path):
    html = tmp_path / "report.html"
    html.write_text("<html><body><h1>Relatório</h1></body></html>", encoding="utf-8")

    pdf = html_to_pdf(html, tmp_path / "report.pdf")

    assert pdf.read_bytes().startswith(b"%PDF")


@needs_chromium
def test_missing_html_file_raises_a_clear_error(tmp_path: Path):
    with pytest.raises(PdfGenerationError):
        html_to_pdf(tmp_path / "missing.html", tmp_path / "out.pdf")
