"""Tests for write_outputs (rich + target + csv)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from mag.models import Cell, CellValue, Field, PaperResult, RunMeta, SampleKey
from mag.output.writers import write_outputs


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
                cells={"Study 1 - college sample": Cell(values=[CellValue(value=675)])},
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


def test_writes_three_files_and_returns_paths(tmp_path):
    paths = write_outputs(_paper(), tmp_path)
    assert paths["rich"].is_file() and paths["target"].is_file() and paths["csv"].is_file()
    assert paths["rich"].name == "paper_rich.json"
    assert paths["target"].name == "paper_target.json"
    assert paths["csv"].name == "paper.csv"


def test_target_json_is_flat_and_loadable(tmp_path):
    paths = write_outputs(_paper(), tmp_path)
    target = json.loads(paths["target"].read_text(encoding="utf-8"))
    assert target["Author"] == "Tylka"
    assert target["Sample"] == {"Study 1 - college sample": [675]}


def test_rich_json_roundtrips_to_paper_result(tmp_path):
    paths = write_outputs(_paper(), tmp_path)
    again = PaperResult.model_validate_json(paths["rich"].read_text(encoding="utf-8"))
    assert again.paper_id == "1Tylka2015"
    assert again.fields["Sample"].cells["Study 1 - college sample"].values[0].value == 675
