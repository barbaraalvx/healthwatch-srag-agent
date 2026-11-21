"""Per-run audit trail: one JSON line per event in audit.jsonl, plus manifest.json at the end."""

import json
import uuid
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from srag.audit.events import EventDetails, EventType
from srag.audit.manifest import (
    MANIFEST_FILENAME,
    ManifestInfo,
    file_sha256,
    git_commit,
    write_manifest_file,
)
from srag.audit.sanitize import Sanitizer
from srag.config import AUDIT_MAX_ITEMS, AUDIT_MAX_TEXT_CHARS

AUDIT_FILENAME = "audit.jsonl"
FOLDER_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuditLogger:
    """Writes sanitized events for one run and keeps its token and cost totals."""

    def __init__(
        self, run_dir: Path, run_id: str, secrets: Iterable[str] = (), clock: Clock = _utc_now
    ) -> None:
        self.run_id = run_id
        self.run_dir = run_dir
        self._clock = clock
        self._started_at = clock()
        self._sanitizer = Sanitizer(secrets, AUDIT_MAX_TEXT_CHARS, AUDIT_MAX_ITEMS)
        self._events = 0
        self._tokens_in = 0
        self._tokens_out = 0
        self._cost_usd = 0.0

    @classmethod
    def create(
        cls, reports_dir: Path, secrets: Iterable[str] = (), clock: Clock = _utc_now
    ) -> "AuditLogger":
        """Start a new run: new run_id and folder reports/<timestamp>_<run_id>/."""
        run_id = str(uuid.uuid4())
        stamp = clock().strftime(FOLDER_TIMESTAMP_FORMAT)
        run_dir = reports_dir / f"{stamp}_{run_id}"
        run_dir.mkdir(parents=True)
        return cls(run_dir, run_id, secrets, clock)

    @property
    def audit_path(self) -> Path:
        return self.run_dir / AUDIT_FILENAME

    def log_event(
        self, event_type: EventType, node: str, details: EventDetails | None = None
    ) -> None:
        """Append one sanitized event."""
        details = details or EventDetails()
        record = {
            "run_id": self.run_id,
            "timestamp": self._clock().isoformat(timespec="milliseconds"),
            "event_type": event_type.value,
            "node": node,
            **{key: value for key, value in asdict(details).items() if value is not None},
        }
        line = json.dumps(self._sanitizer.clean(record), ensure_ascii=False)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        self._add_to_totals(details)

    def write_manifest(self, info: ManifestInfo, status: str) -> Path:
        """Write manifest.json with the run configuration, provenance, status and totals."""
        content = {
            "run_id": self.run_id,
            "started_at": self._started_at.isoformat(timespec="seconds"),
            "finished_at": self._clock().isoformat(timespec="seconds"),
            "status": status,
            "scope": info.uf or "BR",
            "model": info.model,
            "prompt_versions": info.prompt_versions,
            "data_file_sha256": file_sha256(info.data_file) if info.data_file else None,
            "data_max_date": info.data_max_date,
            "git_commit": git_commit(),
            "totals": {
                "events": self._events,
                "tokens_in": self._tokens_in,
                "tokens_out": self._tokens_out,
                "cost_usd": round(self._cost_usd, 6),
            },
        }
        cleaned = self._sanitizer.clean(content)
        return write_manifest_file(self.run_dir / MANIFEST_FILENAME, cleaned)

    def _add_to_totals(self, details: EventDetails) -> None:
        self._events += 1
        self._tokens_in += details.tokens_in or 0
        self._tokens_out += details.tokens_out or 0
        self._cost_usd += details.cost_usd or 0.0
