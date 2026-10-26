"""Tests for mag.models core contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from mag.models import (
    Cell,
    CellValue,
    Derivation,
    EvidenceRecord,
    Field,
    PaperResult,
    RunMeta,
    SampleKey,
    Warning,
)


def test_samplekey_rendered_with_label():
    assert (
        SampleKey(study_index=2, sample_label="college sample").rendered
        == "Study 2 - college sample"
    )


def test_samplekey_rendered_single_study():
    assert SampleKey(study_index=1, sample_label="Single study").rendered == "Study 1"
    assert SampleKey(study_index=1, sample_label="").rendered == "Study 1"


def test_samplekey_is_hashable_and_frozen():
    k = SampleKey(study_index=1, sample_label="a")
    assert k in {k}
    with pytest.raises(ValidationError):
        k.study_index = 9  # frozen


def test_cellvalue_confidence_bounds():
    CellValue(value=5, confidence=0.5)
    with pytest.raises(ValidationError):
        CellValue(value=5, confidence=1.5)


def test_evidence_bbox_length():
    EvidenceRecord(
        pdf_name="p.pdf", section_id="003", granularity="paragraph", quote="q", bbox=[0, 0, 1, 1]
    )
    with pytest.raises(ValidationError):
        EvidenceRecord(
            pdf_name="p.pdf", section_id="003", granularity="paragraph", quote="q", bbox=[0, 0, 1]
        )


def test_field_paper_scope_rejects_cells():
    with pytest.raises(ValidationError):
        Field(name="Author", scope="paper", cells={"Study 1": Cell(values=[])})


def test_field_sample_scope_rejects_paper_value():
    with pytest.raises(ValidationError):
        Field(name="Sample", scope="sample", paper_value=CellValue(value=1))


def test_derivation_roundtrip():
    d = Derivation(
        kind="weighted_mean",
        skill_name="compute_weighted_mean_total",
        inputs={"f": 24.21, "m": 25.02},
        formula="(...)/675",
    )
    assert d.kind == "weighted_mean"


def test_runmeta_timestamp_order():
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        RunMeta(
            run_id="r",
            provider="gemini",
            model="gemini-2.5-flash",
            schema_name="bas-bmi",
            schema_version=1,
            started_at=now,
            finished_at=now.replace(year=now.year - 1),
        )


def test_paperresult_roundtrips_json():
    now = datetime.now(UTC)
    pr = PaperResult(
        paper_id="1Tylka2015",
        pdf_path="/x/1Tylka2015.pdf",
        marker_output_dir="/x/marker",
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
        warnings=[Warning(code="x", message="m")],
        run_meta=RunMeta(
            run_id="r",
            provider="gemini",
            model="gemini-2.5-flash",
            schema_name="bas-bmi",
            schema_version=1,
            started_at=now,
            finished_at=now,
        ),
    )
    dumped = pr.model_dump_json()
    again = PaperResult.model_validate_json(dumped)
    assert again.fields["Sample"].cells["Study 1 - college sample"].values[0].value == 675


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        CellValue(value=1, bogus=2)
    with pytest.raises(ValidationError):
        SampleKey(study_index=1, sample_label="a", junk=3)
