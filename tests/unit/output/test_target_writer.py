"""Tests for the flat target-shape writer."""

from __future__ import annotations

from datetime import UTC, datetime

from mag.models import Cell, CellValue, Field, PaperResult, RunMeta, SampleKey
from mag.output.target_writer import to_target_dict


def _paper() -> PaperResult:
    now = datetime.now(UTC)
    return PaperResult(
        paper_id="1Tylka2015",
        pdf_path="/x/1Tylka2015.pdf",
        marker_output_dir="/x/marker",
        samples=[SampleKey(study_index=1, sample_label="college sample")],
        fields={
            "Author": Field(name="Author", scope="paper", paper_value=CellValue(value="Tylka")),
            "Number of studies": Field(
                name="Number of studies", scope="paper", paper_value=CellValue(value=3)
            ),
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
            "Mean BMI of participants": Field(
                name="Mean BMI of participants",
                scope="sample",
                gender_specific=True,
                cells={"Study 1 - college sample": Cell(values=[])},
            ),  # absent
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


def test_paper_scope_fields_are_top_level_scalars():
    d = to_target_dict(_paper())
    assert d["Author"] == "Tylka"
    assert d["Number of studies"] == 3


def test_sample_scope_field_is_keyed_by_rendered_sample():
    d = to_target_dict(_paper())
    assert d["Sample"] == {"Study 1 - college sample": [675, 367, 308]}


def test_empty_cell_serializes_as_empty_list():
    d = to_target_dict(_paper())
    assert d["Mean BMI of participants"] == {"Study 1 - college sample": []}


def test_all_none_cell_collapses_to_empty_list():
    paper = _paper()
    paper.fields["Mean BMI of participants"].cells["Study 1 - college sample"] = Cell(
        values=[CellValue(value=None), CellValue(value=None), CellValue(value=None)]
    )
    d = to_target_dict(paper)
    assert d["Mean BMI of participants"] == {"Study 1 - college sample": []}


def test_all_declared_samples_shown_even_without_a_cell():
    # A field that resolved no cell for a declared sample still lists it as [].
    paper = _paper()
    paper.samples.append(SampleKey(study_index=2, sample_label="community sample"))
    d = to_target_dict(paper)
    assert d["Sample"]["Study 2 - community sample"] == []


def test_field_order_preserved():
    d = to_target_dict(_paper())
    assert list(d.keys()) == ["Author", "Number of studies", "Sample", "Mean BMI of participants"]


def test_sample_field_zero_normalized_to_none():
    # An all-women sample reports male count as 0; it must be emitted as None.
    paper = _paper()
    paper.fields["Sample"].cells["Study 1 - college sample"] = Cell(
        values=[CellValue(value=215), CellValue(value=215), CellValue(value=0)]
    )
    d = to_target_dict(paper)
    assert d["Sample"]["Study 1 - college sample"] == [215, 215, None]


def test_non_sample_field_zero_preserved():
    # A 0 in a non-Sample field (e.g. Percent of white) must NOT be converted to None.
    paper = _paper()
    paper.fields["Percent of white in participants"] = Field(
        name="Percent of white in participants",
        scope="sample",
        gender_specific=False,
        cells={"Study 1 - college sample": Cell(values=[CellValue(value=0)])},
    )
    d = to_target_dict(paper)
    assert d["Percent of white in participants"]["Study 1 - college sample"] == [0]
