"""Exports docs/architecture.svg to docs/architecture.pdf and docs/architecture.png.

The SVG is the diagram source (edit it directly). Needs Chromium:
uv run playwright install chromium. Usage: uv run python scripts/export_architecture.py
"""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
SOURCE = DOCS_DIR / "architecture.svg"
SCREENSHOT_SCALE = 2
VIEW_BOX = re.compile(r'viewBox="0 0 (\d+) (\d+)"')

PAGE_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: {width}px {height}px; margin: 0; }}
  html, body {{ margin: 0; background: #ffffff; }}
  svg {{ display: block; }}
</style></head><body>{svg}</body></html>
"""


def main() -> None:
    svg = SOURCE.read_text(encoding="utf-8")
    width, height = (int(value) for value in VIEW_BOX.search(svg).groups())
    page_html = PAGE_TEMPLATE.format(width=width, height=height, svg=svg)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(
                viewport={"width": width, "height": height}, device_scale_factor=SCREENSHOT_SCALE
            )
            page.set_content(page_html)
            page.screenshot(path=str(DOCS_DIR / "architecture.png"))
            page.pdf(
                path=str(DOCS_DIR / "architecture.pdf"),
                width=f"{width}px",
                height=f"{height}px",
                print_background=True,
                page_ranges="1",
            )
        finally:
            browser.close()
    print(f"Wrote {DOCS_DIR / 'architecture.pdf'} and {DOCS_DIR / 'architecture.png'}")


if __name__ == "__main__":
    main()
