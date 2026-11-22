"""Renders the report context into a standalone HTML page."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from srag.report.context import ReportContext

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "report.html.j2"

_ENVIRONMENT = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=True,  # everything is escaped except Markdown already converted to safe HTML
    undefined=StrictUndefined,
)


def render_report(context: ReportContext) -> str:
    """The full HTML document, with charts embedded so the file works on its own."""
    return _ENVIRONMENT.get_template(TEMPLATE_NAME).render(report=context)
