"""Run limits: iterations, cost and wall-clock time. Exceeding one stops the run."""

import time
from collections.abc import Callable

from srag.config import Settings

TOKENS_PER_MILLION = 1_000_000


class LimitExceededError(RuntimeError):
    """Raised when a run limit is exceeded; `reason` is recorded in the audit trail."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def llm_cost_usd(tokens_in: int, tokens_out: int, settings: Settings) -> float:
    """Cost of one LLM call from the configured prices per million tokens."""
    input_cost = tokens_in * settings.llm_price_input_per_mtok
    output_cost = tokens_out * settings.llm_price_output_per_mtok
    return (input_cost + output_cost) / TOKENS_PER_MILLION


class RunLimits:
    """Tracks one run against the iteration, cost and time limits from the settings."""

    REASON_ITERATIONS = "max_iterations_exceeded"
    REASON_COST = "max_cost_exceeded"
    REASON_TIMEOUT = "run_timeout_exceeded"

    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic) -> None:
        self._max_iterations = settings.agent_max_iterations
        self._max_cost_usd = settings.max_cost_usd_per_run
        self._timeout_seconds = settings.run_timeout_seconds
        self._clock = clock
        self._started_at = clock()
        self.iterations = 0
        self.cost_usd = 0.0

    def count_iteration(self) -> None:
        """Register one agent step; raise when the step limit would be passed."""
        self.check_timeout()
        if self.iterations >= self._max_iterations:
            raise LimitExceededError(
                self.REASON_ITERATIONS, f"Agent stopped after {self._max_iterations} iterations"
            )
        self.iterations += 1

    def add_cost(self, cost_usd: float) -> None:
        """Add the cost of a call; raise once the total is above the limit."""
        self.cost_usd += cost_usd
        if self.cost_usd > self._max_cost_usd:
            raise LimitExceededError(
                self.REASON_COST,
                f"Run cost ${self.cost_usd:.4f} is above the ${self._max_cost_usd:.4f} limit",
            )

    def check_timeout(self) -> None:
        """Raise when the run has been going for longer than the allowed time."""
        if self._clock() - self._started_at > self._timeout_seconds:
            raise LimitExceededError(
                self.REASON_TIMEOUT, f"Run took longer than {self._timeout_seconds} seconds"
            )
