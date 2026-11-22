import re

import pytest

from srag.agent.fallback import REASON_LLM_ERROR, REASON_VALIDATION_FAILED, fallback_text
from srag.agent.prompt_loader import PROMPTS_DIR, load_prompt
from srag.agent.tools import GET_CASE_SERIES, GET_METRICS, SEARCH_NEWS
from srag.config import (
    MEDICAL_DISCLAIMER,
    ORCHESTRATOR_PROMPT,
    REQUIRED_REPORT_SECTIONS,
    WRITER_PROMPT,
)
from srag.guardrails.output import check_disclaimer, check_sections
from srag.news.untrusted_block import UNTRUSTED_OPEN


def test_the_active_prompts_exist_and_are_not_empty():
    for name in (ORCHESTRATOR_PROMPT, WRITER_PROMPT):
        prompt = load_prompt(name)

        assert prompt.name == name
        assert len(prompt.text) > 200


@pytest.mark.parametrize(
    "name", ["writer", "../secrets_v1", "Writer_v1", "writer_v1.md", "", "a_v"]
)
def test_invalid_prompt_names_are_rejected(name):
    with pytest.raises(ValueError):
        load_prompt(name)


def test_every_prompt_file_has_a_version_suffix():
    names = [path.stem for path in PROMPTS_DIR.glob("*.md")]

    assert names
    assert all(re.fullmatch(r".+_v\d+", name) for name in names)


def test_the_orchestrator_prompt_names_every_tool():
    text = load_prompt(ORCHESTRATOR_PROMPT).text

    assert all(tool in text for tool in (GET_METRICS, GET_CASE_SERIES, SEARCH_NEWS))


def test_the_writer_prompt_asks_for_the_sections_the_guardrail_requires():
    text = load_prompt(WRITER_PROMPT).text

    assert all(f"## {section}" in text for section in REQUIRED_REPORT_SECTIONS)
    assert UNTRUSTED_OPEN in text


@pytest.mark.parametrize(
    "reason", [REASON_VALIDATION_FAILED, REASON_LLM_ERROR, "max_cost_exceeded", "anything else"]
)
def test_fallback_text_passes_the_output_guardrail_checks(reason):
    text = fallback_text(reason)

    assert check_sections(text) == []
    assert check_disclaimer(text) == []
    assert not re.search(r"\d", text.replace(MEDICAL_DISCLAIMER, ""))


def test_fallback_text_explains_each_reason_in_plain_language():
    assert "limite de custo" in fallback_text("max_cost_exceeded")
    assert "tempo máximo" in fallback_text("run_timeout_exceeded")
    assert "limite de etapas" in fallback_text("max_iterations_exceeded")
    assert "motivo não especificado" in fallback_text("something_new")
