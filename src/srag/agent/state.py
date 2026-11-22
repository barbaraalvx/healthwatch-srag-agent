"""Typed state shared by the nodes of the agent graph."""

from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from srag.guardrails.output import ValidationResult
from srag.metrics.snapshot import MetricsSnapshot
from srag.news.models import NewsItem

STATUS_COMPLETED = "completed"
STATUS_FALLBACK = "fallback"
STATUS_STOPPED = "stopped"


class AgentState(TypedDict, total=False):
    """Keys appear as the run advances; routing tests for presence with `in` / `.get`."""

    messages: Annotated[list[AnyMessage], add_messages]
    snapshot: MetricsSnapshot
    daily_chart: Path
    monthly_chart: Path
    news_items: tuple[NewsItem, ...]
    searches_done: int
    draft: str
    draft_truncated: bool
    validation: ValidationResult
    writer_attempts: int
    report_text: str
    status: str
    stop_reason: str
