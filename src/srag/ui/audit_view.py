"""Reads the files of a run (audit.jsonl, manifest.json) into shapes the UI can show."""

import json
from pathlib import Path
from typing import Any

import pandas as pd

AUDIT_COLUMNS = (
    "timestamp",
    "event_type",
    "node",
    "decision",
    "reason",
    "model",
    "prompt_version",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "duration_ms",
    "output_summary",
)


def load_audit_table(audit_path: Path) -> pd.DataFrame:
    """One row per audit event, with a fixed set of columns (missing values stay empty)."""
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    table = pd.DataFrame(events).reindex(columns=AUDIT_COLUMNS)
    table["output_summary"] = table["output_summary"].map(_as_text)
    return table


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _as_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
