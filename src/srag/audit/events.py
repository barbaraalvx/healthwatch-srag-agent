"""Event types and the optional details recorded for each audit event."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    NODE_START = "node_start"
    NODE_END = "node_end"
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    GUARDRAIL = "guardrail"
    ERROR = "error"


@dataclass(frozen=True)
class EventDetails:
    """Everything an event may carry besides its type and node; None fields are not logged."""

    inputs: Mapping[str, Any] | None = None
    output_summary: Mapping[str, Any] | str | None = None
    model: str | None = None
    prompt_version: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    duration_ms: int | None = None
    decision: str | None = None
    reason: str | None = None
