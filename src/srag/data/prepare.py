"""Build data/processed/srag.parquet and a quality report from the raw DATASUS CSV files."""

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from srag.config import get_settings
from srag.data import schema
from srag.data.cleaning import CleaningResult, clean

logger = logging.getLogger(__name__)


class NoRawFilesError(FileNotFoundError):
    """Raised when the raw data folder has no CSV files."""


def read_raw_files(raw_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    """Read only the needed columns of every CSV in raw_dir, as text."""
    files = sorted(raw_dir.glob("*.csv"))
    if not files:
        raise NoRawFilesError(f"No CSV files found in {raw_dir}")
    frames = [
        pd.read_csv(
            path,
            sep=schema.CSV_SEPARATOR,
            encoding=schema.CSV_ENCODING,
            usecols=list(schema.RAW_COLUMNS),
            dtype=str,
        )
        for path in files
    ]
    return pd.concat(frames, ignore_index=True), [path.name for path in files]


def build_quality_report(result: CleaningResult, source_files: list[str]) -> dict:
    """Summarize the preparation with aggregates only (no row-level data)."""
    cases = result.cases
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_files": source_files,
        "rows_read": result.rows_read,
        "rows_kept": len(cases),
        "rows_dropped": result.dropped,
        "missing_percent": (cases.isna().mean() * 100).round(1).to_dict(),
        "case_date_min": cases[schema.CASE_DATE].min().date().isoformat(),
        "case_date_max": cases[schema.CASE_DATE].max().date().isoformat(),
    }


def prepare(raw_dir: Path, output_path: Path, today: date) -> dict:
    """Clean the raw files, write the Parquet file and the quality report, return the report."""
    raw, source_files = read_raw_files(raw_dir)
    result = clean(raw, today)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.cases.to_parquet(output_path, index=False)
    report = build_quality_report(result, source_files)
    report_path = output_path.with_name(schema.QUALITY_REPORT_FILENAME)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Wrote %s rows to %s", report["rows_kept"], output_path)
    return report


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    report = prepare(settings.data_raw_dir, settings.data_processed_path, date.today())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
