"""Builds the real chat model. Claude Haiku 5.5 rejects temperature, so none is sent."""

from langchain_anthropic import ChatAnthropic

from srag.config import LLM_MAX_RETRIES, Settings


def build_chat_model(settings: Settings) -> ChatAnthropic:
    """Chat model with the configured model name, token cap, timeout and reasoning effort."""
    return ChatAnthropic(
        model=settings.llm_model,
        api_key=settings.anthropic_api_key,
        max_tokens=settings.llm_max_tokens,
        default_request_timeout=settings.llm_timeout_seconds,
        max_retries=LLM_MAX_RETRIES,
        effort=settings.llm_effort,
    )
