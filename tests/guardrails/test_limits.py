import pytest

from srag.config import Settings
from srag.guardrails.limits import LimitExceededError, RunLimits, llm_cost_usd


class FakeClock:
    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        agent_max_iterations=3,
        max_cost_usd_per_run=0.10,
        run_timeout_seconds=60,
        llm_price_input_per_mtok=0.10,
        llm_price_output_per_mtok=0.50,
    )


def test_llm_cost_uses_the_price_per_million_tokens(settings):
    assert llm_cost_usd(1_000_000, 1_000_000, settings) == pytest.approx(0.60)
    assert llm_cost_usd(2_000, 500, settings) == pytest.approx(0.00045)
    assert llm_cost_usd(0, 0, settings) == 0.0


def test_iterations_up_to_the_limit_are_allowed(settings):
    limits = RunLimits(settings)

    for _ in range(3):
        limits.count_iteration()

    assert limits.iterations == 3


def test_one_iteration_over_the_limit_stops_the_run(settings):
    limits = RunLimits(settings)
    for _ in range(3):
        limits.count_iteration()

    with pytest.raises(LimitExceededError) as raised:
        limits.count_iteration()

    assert raised.value.reason == RunLimits.REASON_ITERATIONS
    assert limits.iterations == 3


def test_cost_exactly_at_the_limit_is_allowed(settings):
    limits = RunLimits(settings)

    limits.add_cost(0.06)
    limits.add_cost(0.04)

    assert limits.cost_usd == pytest.approx(0.10)


def test_cost_above_the_limit_stops_the_run(settings):
    limits = RunLimits(settings)
    limits.add_cost(0.08)

    with pytest.raises(LimitExceededError) as raised:
        limits.add_cost(0.05)

    assert raised.value.reason == RunLimits.REASON_COST
    assert "0.1300" in str(raised.value)


def test_timeout_stops_the_run_only_after_the_allowed_time(settings):
    clock = FakeClock()
    limits = RunLimits(settings, clock)

    clock.seconds = 60
    limits.check_timeout()
    clock.seconds = 60.5

    with pytest.raises(LimitExceededError) as raised:
        limits.check_timeout()
    assert raised.value.reason == RunLimits.REASON_TIMEOUT


def test_a_new_iteration_also_checks_the_timeout(settings):
    clock = FakeClock()
    limits = RunLimits(settings, clock)
    clock.seconds = 100

    with pytest.raises(LimitExceededError) as raised:
        limits.count_iteration()

    assert raised.value.reason == RunLimits.REASON_TIMEOUT
    assert limits.iterations == 0
