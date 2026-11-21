import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from srag.data import schema
from srag.data.prepare import NoRawFilesError, prepare

SAMPLE_CSV = Path(__file__).parents[1] / "fixtures" / "srag_sample.csv"
TODAY = date(2026, 6, 1)


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "raw"
    folder.mkdir()
    shutil.copy(SAMPLE_CSV, folder / "sample.csv")
    return folder


def test_prepare_writes_parquet_without_identifying_columns(raw_dir: Path, tmp_path: Path):
    output = tmp_path / "processed" / "srag.parquet"

    prepare(raw_dir, output, TODAY)

    assert tuple(pd.read_parquet(output).columns) == schema.PROCESSED_COLUMNS


def test_prepare_writes_quality_report_with_aggregates_only(raw_dir: Path, tmp_path: Path):
    output = tmp_path / "processed" / "srag.parquet"

    prepare(raw_dir, output, TODAY)

    report = json.loads((output.parent / schema.QUALITY_REPORT_FILENAME).read_text("utf-8"))
    assert report["rows_read"] == 13
    assert report["rows_kept"] == 9
    assert report["source_files"] == ["sample.csv"]
    assert report["case_date_min"] == "2026-01-10"
    assert report["case_date_max"] == "2026-01-15"
    assert "PACIENTE" not in json.dumps(report)


def test_prepare_fails_clearly_when_there_are_no_csv_files(tmp_path: Path):
    with pytest.raises(NoRawFilesError):
        prepare(tmp_path, tmp_path / "out.parquet", TODAY)
