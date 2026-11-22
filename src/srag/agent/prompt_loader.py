"""Loads versioned prompt files from agent/prompts (name_v1.md, name_v2.md, ...)."""

import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"
_PROMPT_NAME = re.compile(r"[a-z]+(?:_[a-z]+)*_v\d+")


@dataclass(frozen=True)
class Prompt:
    name: str
    text: str


def load_prompt(name: str) -> Prompt:
    """Read prompts/<name>.md; the name must end with a version suffix such as _v1."""
    if not _PROMPT_NAME.fullmatch(name):
        raise ValueError(f"Invalid prompt name: {name!r} (expected e.g. 'writer_v1')")
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
    return Prompt(name=name, text=text)
