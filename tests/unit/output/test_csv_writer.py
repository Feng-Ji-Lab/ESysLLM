"""Tests for the tidy CSV writer."""

from __future__ import annotations

import csv
from datetime import UTC, datetime

from mag.models import Cell, CellValue, Field, PaperResult, RunMeta, SampleKey
from mag.output.csv_writer import to_rows, write_csv


def _paper() -> PaperResult:
    now = datetime.now(UTC)
    return PaperResult(
        paper_id="1Tylka2015",
        pdf_path="/x.pdf",
        marker_output_dir="/m",
        samples=[SampleKey(study_index=1, sample_label="college sample")],
        fields={
            "Author": Field(name="Author", scope="paper", paper_value=CellValue(value="Tylka")),
            "Sample": Field(
                name="Sample",
                scope="sample",
                gender_specific=True,
                cells={
                    "Study 1 - college sample": Cell(
                        values=[CellValue(value=675), CellValue(value=367), CellValue(value=308)]
                    )
                },
            ),
        },
        warnings=[],
        run_meta=RunMeta(
            run_id="r",
            provider="gemini",
            model="m",
            schema_name="bas-bmi",
            schema_version=2,
            started_at=now,
            finished_at=now,
        ),
    )


def test_rows_cover_paper_and_sample_fields():
    rows = to_rows(_paper())
    author = next(r for r in rows if r["field"] == "Author")
    assert author["sample_key"] == "" and author["value"] == '"Tylka"'
    sample = next(r for r in rows if r["field"] == "Sample")
    assert sample["sample_key"] == "Study 1 - college sample"
    assert sample["value"] == "[675, 367, 308]"
    assert all(r["paper_id"] == "1Tylka2015" for r in rows)


def test_write_csv_roundtrips(tmp_path):
    path = tmp_path / "paper.csv"
    write_csv(_paper(), path)
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert {"paper_id", "sample_key", "field", "value"} == set(rows[0].keys())
    sample = next(r for r in rows if r["field"] == "Sample")
    assert sample["value"] == "[675, 367, 308]"
