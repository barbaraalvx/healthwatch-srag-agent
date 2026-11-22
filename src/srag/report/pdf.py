"""HTML to PDF with a headless Chromium (Playwright)."""

from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

PAGE_FORMAT = "A4"
PAGE_MARGIN = {"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"}


class PdfGenerationError(RuntimeError):
    """Raised when the PDF could not be created (for example, Chromium is not installed)."""


def html_to_pdf(html_path: Path, pdf_path: Path) -> Path:
    """Open the HTML file in Chromium and save it as an A4 PDF."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(html_path.resolve().as_uri())
                page.pdf(
                    path=str(pdf_path),
                    format=PAGE_FORMAT,
                    margin=PAGE_MARGIN,
                    print_background=True,
                )
            finally:
                browser.close()
    except PlaywrightError as error:
        raise PdfGenerationError(f"PDF generation failed: {type(error).__name__}") from error
    return pdf_path
