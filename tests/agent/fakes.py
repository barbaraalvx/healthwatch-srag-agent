"""Fake model and news searcher for agent tests: no API keys, no network, no cost."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from srag.news.client import NewsSearchError


class FakeChatModel(BaseChatModel):
    """Plays back scripted answers (messages or exceptions) and records what it was asked."""

    script: list[Any]
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(list(messages))
        if not self.script:
            raise AssertionError("The fake model was called more times than scripted")
        answer = self.script.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ChatResult(generations=[ChatGeneration(message=answer)])

    def bind_tools(self, tools, **kwargs):
        return self


def usage(tokens_in: int, tokens_out: int) -> dict[str, int]:
    return {
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "total_tokens": tokens_in + tokens_out,
    }


def tool_calls_message(*calls: tuple[str, dict], tokens_in: int = 1000) -> AIMessage:
    """An orchestrator answer that asks for tools, e.g. ('search_news', {'query': 'SRAG'})."""
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call_{index}"}
            for index, (name, args) in enumerate(calls)
        ],
        usage_metadata=usage(tokens_in, 100),
    )


def text_message(
    text: str, tokens_in: int = 2000, tokens_out: int = 300, stop_reason: str | None = None
) -> AIMessage:
    metadata = {"stop_reason": stop_reason} if stop_reason else {}
    return AIMessage(
        content=text, usage_metadata=usage(tokens_in, tokens_out), response_metadata=metadata
    )


def done_message() -> AIMessage:
    """An orchestrator answer that ends the collection without calling tools."""
    return text_message("Coleta concluída.", tokens_in=500, tokens_out=5)


class FakeSearcher:
    """Returns one scripted batch of raw results per search (or raises a scripted error)."""

    def __init__(self, batches: list[Any]) -> None:
        self.batches = batches
        self.queries: list[str] = []

    def search(self, query: str) -> list[dict[str, Any]]:
        self.queries.append(query)
        batch = self.batches.pop(0)
        if isinstance(batch, Exception):
            raise batch
        return batch


def news_result(number: int = 1) -> dict[str, Any]:
    """A raw Tavily-like result that passes the sanitizer and the relevance filter."""
    return {
        "title": f"InfoGripe {number}: casos de SRAG em alerta",
        "url": f"https://agencia.fiocruz.br/infogripe-{number}",
        "content": "O boletim InfoGripe mostra sinal de crescimento de casos de SRAG.",
    }


def search_error() -> NewsSearchError:
    return NewsSearchError("News search failed (UsageLimitExceededError)")
