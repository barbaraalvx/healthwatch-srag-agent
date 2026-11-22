import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from srag.audit.events import EventDetails, EventType
from srag.audit.logger import AuditLogger
from srag.audit.manifest import ManifestInfo

START = datetime(2026, 11, 21, 12, 0, 0, tzinfo=UTC)


class FakeClock:
    """Moves one second forward on every call, so timestamps are distinct and predictable."""

    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        current = self.now
        self.now += timedelta(seconds=1)
        return current


@pytest.fixture
def logger(tmp_path: Path) -> AuditLogger:
    return AuditLogger.create(tmp_path / "reports", clock=FakeClock())


def read_events(logger: AuditLogger) -> list[dict]:
    lines = logger.audit_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_create_makes_a_folder_named_after_timestamp_and_run_id(tmp_path: Path):
    logger = AuditLogger.create(tmp_path / "reports", clock=FakeClock())

    assert uuid.UUID(logger.run_id).version == 4
    assert logger.run_dir == tmp_path / "reports" / f"20261121T120000Z_{logger.run_id}"
    assert logger.run_dir.is_dir()


def test_each_run_gets_its_own_id_and_folder(tmp_path: Path):
    first = AuditLogger.create(tmp_path, clock=FakeClock())
    second = AuditLogger.create(tmp_path, clock=FakeClock())

    assert first.run_id != second.run_id
    assert first.run_dir != second.run_dir


def test_event_is_one_json_line_with_the_required_fields(logger: AuditLogger):
    details = EventDetails(
        inputs={"uf": "SP"},
        output_summary="ok",
        model="claude-haiku-5-5",
        prompt_version="writer_v1",
        tokens_in=100,
        tokens_out=20,
        cost_usd=0.00002,
        duration_ms=350,
        decision="pass",
        reason="all checks passed",
    )

    logger.log_event(EventType.LLM_CALL, "writer", details)

    (event,) = read_events(logger)
    assert event["run_id"] == logger.run_id
    assert event["event_type"] == "llm_call"
    assert event["node"] == "writer"
    assert event["timestamp"].startswith("2026-11-21T12:00:0")
    assert event["inputs"] == {"uf": "SP"}
    assert (event["tokens_in"], event["tokens_out"], event["duration_ms"]) == (100, 20, 350)
    assert (event["decision"], event["reason"]) == ("pass", "all checks passed")


def test_fields_without_a_value_are_not_written(logger: AuditLogger):
    logger.log_event(EventType.NODE_START, "orchestrator")

    (event,) = read_events(logger)
    assert set(event) == {"run_id", "timestamp", "event_type", "node"}


def test_events_are_appended_in_order(logger: AuditLogger):
    for node in ("a", "b", "c"):
        logger.log_event(EventType.NODE_END, node)

    assert [event["node"] for event in read_events(logger)] == ["a", "b", "c"]


def test_accents_are_written_as_they_are(logger: AuditLogger):
    logger.log_event(EventType.GUARDRAIL, "output", EventDetails(reason="Análise ausente"))

    assert "Análise ausente" in logger.audit_path.read_text(encoding="utf-8")


def test_secrets_never_reach_the_audit_file_or_the_manifest(tmp_path: Path):
    secret = "sk-ant-supersecretvalue123"
    logger = AuditLogger.create(tmp_path, secrets=[secret], clock=FakeClock())

    logger.log_event(
        EventType.ERROR,
        "tool",
        EventDetails(inputs={"api_key": secret, "note": f"failed with {secret}"}, reason=secret),
    )
    logger.write_manifest(ManifestInfo(uf=None, model=secret), "failed")

    for file in logger.run_dir.iterdir():
        assert secret not in file.read_text(encoding="utf-8")


def test_manifest_has_config_provenance_status_and_totals(logger: AuditLogger, tmp_path: Path):
    data_file = tmp_path / "srag.parquet"
    data_file.write_bytes(b"fake parquet content")
    logger.log_event(
        EventType.LLM_CALL, "writer", EventDetails(tokens_in=100, tokens_out=20, cost_usd=0.001)
    )
    logger.log_event(
        EventType.LLM_CALL, "writer", EventDetails(tokens_in=50, tokens_out=10, cost_usd=0.0005)
    )
    logger.log_event(EventType.NODE_END, "writer")
    info = ManifestInfo(
        uf="SP",
        model="claude-haiku-5-5",
        effort="low",
        prompt_versions={"writer": "v1"},
        data_file=data_file,
        data_max_date=datetime(2026, 11, 15).date(),
    )

    path = logger.write_manifest(info, "completed")

    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert path == logger.run_dir / "manifest.json"
    assert manifest["run_id"] == logger.run_id
    assert manifest["status"] == "completed"
    assert manifest["scope"] == "SP"
    assert manifest["model"] == "claude-haiku-5-5"
    assert manifest["effort"] == "low"
    assert manifest["prompt_versions"] == {"writer": "v1"}
    assert manifest["data_file_sha256"] == hashlib.sha256(b"fake parquet content").hexdigest()
    assert manifest["data_max_date"] == "2026-11-15"
    assert "git_commit" in manifest
    assert manifest["totals"] == {
        "events": 3,
        "tokens_in": 150,
        "tokens_out": 30,
        "cost_usd": 0.0015,
    }
    assert manifest["started_at"] < manifest["finished_at"]


def test_manifest_scope_is_br_for_the_whole_country(logger: AuditLogger):
    path = logger.write_manifest(ManifestInfo(uf=None, model="m"), "completed")

    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["scope"] == "BR"
    assert manifest["data_file_sha256"] is None
