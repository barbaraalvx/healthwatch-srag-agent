import json
from pathlib import Path

from srag.ui.audit_view import AUDIT_COLUMNS, load_audit_table, load_manifest


def write_audit(path: Path, events: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    return path


def test_table_has_one_row_per_event_and_fixed_columns(tmp_path):
    audit = write_audit(
        tmp_path / "audit.jsonl",
        [
            {"event_type": "node_start", "node": "orchestrator", "timestamp": "t1"},
            {"event_type": "llm_call", "node": "writer", "tokens_in": 10, "cost_usd": 0.001},
        ],
    )

    table = load_audit_table(audit)

    assert list(table.columns) == list(AUDIT_COLUMNS)
    assert len(table) == 2
    assert table.loc[1, "tokens_in"] == 10
    assert table["tokens_in"].isna()[0]


def test_dict_summaries_are_shown_as_text(tmp_path):
    audit = write_audit(
        tmp_path / "audit.jsonl",
        [
            {"event_type": "tool_call", "node": "tools", "output_summary": {"articles": 3}},
            {"event_type": "error", "node": "pdf", "output_summary": "plain text"},
            {"event_type": "node_end", "node": "writer"},
        ],
    )

    table = load_audit_table(audit)

    assert table.loc[0, "output_summary"] == '{"articles": 3}'
    assert table.loc[1, "output_summary"] == "plain text"
    assert table["output_summary"].isna()[2]


def test_blank_lines_are_ignored(tmp_path):
    audit = tmp_path / "audit.jsonl"
    audit.write_text('{"event_type": "error", "node": "x"}\n\n', encoding="utf-8")

    assert len(load_audit_table(audit)) == 1


def test_manifest_is_loaded_as_a_dict(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"status": "completed", "totals": {"events": 4}}', encoding="utf-8")

    assert load_manifest(manifest)["totals"]["events"] == 4
