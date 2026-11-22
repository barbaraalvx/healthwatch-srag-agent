"""The real chat model is built offline here: the request is inspected, never sent."""

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from srag.agent.llm import build_chat_model
from srag.agent.tools import TOOL_SPECS
from srag.config import Settings

MESSAGES = [SystemMessage("sistema"), HumanMessage("olá")]


def payload_for(settings: Settings, with_tools: bool = False) -> dict:
    model = build_chat_model(settings)
    if with_tools:
        bound = model.bind_tools(TOOL_SPECS)
        return bound.bound._get_request_payload(MESSAGES, **bound.kwargs)
    return model._get_request_payload(MESSAGES)


def test_request_uses_the_configured_model_limits_and_effort():
    settings = Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-fake",
        llm_model="claude-haiku-5-5",
        llm_max_tokens=1234,
        llm_effort="medium",
    )

    payload = payload_for(settings)

    assert payload["model"] == "claude-haiku-5-5"
    assert payload["max_tokens"] == 1234
    assert payload["output_config"] == {"effort": "medium"}


@pytest.mark.parametrize("with_tools", [False, True])
def test_no_sampling_parameters_are_sent_because_haiku_rejects_them(with_tools):
    settings = Settings(_env_file=None, anthropic_api_key="sk-ant-fake")

    payload = payload_for(settings, with_tools)

    for forbidden in ("temperature", "top_p", "top_k", "thinking"):
        assert payload.get(forbidden) is None


def test_default_effort_is_low_to_keep_the_cost_down():
    payload = payload_for(Settings(_env_file=None, anthropic_api_key="sk-ant-fake"))

    assert payload["output_config"] == {"effort": "low"}


def test_tools_are_sent_without_forcing_a_tool_choice():
    payload = payload_for(Settings(_env_file=None, anthropic_api_key="sk-ant-fake"), True)

    assert [tool["name"] for tool in payload["tools"]] == [spec["name"] for spec in TOOL_SPECS]
    assert "tool_choice" not in payload


def test_timeout_and_retries_are_bounded():
    model = build_chat_model(
        Settings(_env_file=None, anthropic_api_key="sk-ant-fake", llm_timeout_seconds=45)
    )

    assert model.default_request_timeout == 45
    assert model.max_retries == 1
