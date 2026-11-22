"""Safe conversion of the writer's Markdown text into HTML sections."""

import re

from markdown_it import MarkdownIt
from markupsafe import Markup

_SECTION_HEADING = re.compile(r"(?m)^##\s+(.+?)\s*$")
# Raw HTML in the text is escaped and unsafe link schemes (javascript:) are refused.
_MARKDOWN = MarkdownIt("commonmark", {"html": False})


def split_sections(text: str) -> dict[str, str]:
    """Map each '## Title' heading to the Markdown body that follows it."""
    headings = list(_SECTION_HEADING.finditer(text))
    sections = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections[heading.group(1)] = text[heading.end() : end].strip()
    return sections


def markdown_to_html(text: str) -> Markup:
    """HTML that is safe to embed in the report (marked so the template does not escape it)."""
    return Markup(_MARKDOWN.render(text))
