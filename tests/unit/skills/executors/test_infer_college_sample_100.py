"""Tests for the college→100% education inference executor."""

from __future__ import annotations

from mag.models import Cell, CellValue, Field
from mag.skills.executors.infer_college_sample_100 import infer_college_sample_100
from mag.skills.loader import Skill

SKILL = Skill(
    name="infer_college_sample_100",
    executor="infer_college_sample_100",
    applies_to=["Percentage of college or higher of participants"],
)
TARGET = "Percentage of college or higher of participants"


def _fields(pct, source):
    return {
        "Source of sample": Field(
            name="Source of sample",
            scope="sample",
            gender_specific=True,
            cells={"S1": Cell(values=[CellValue(value=source)])},
        ),
        TARGET: Field(
            name=TARGET,
            scope="sample",
            gender_specific=False,
            cells={"S1": Cell(values=[CellValue(value=pct)] if pct is not None else [])},
        ),
    }


def test_infers_100_for_college_when_missing():
    out = infer_college_sample_100(
        fields=_fields(pct=None, source="college"), target=TARGET, skill=SKILL
    )
    cell = out.cells["S1"]
    assert cell.values[0].value == 100
    assert cell.values[0].derivation is not None
    assert cell.values[0].derivation.kind == "infer_constant"


def test_does_not_infer_for_community():
    out = infer_college_sample_100(
        fields=_fields(pct=None, source="community"), target=TARGET, skill=SKILL
    )
    assert out.cells["S1"].values == []  # left empty


def test_does_not_override_existing_value():
    out = infer_college_sample_100(
        fields=_fields(pct=82.7, source="college"), target=TARGET, skill=SKILL
    )
    assert out.cells["S1"].values[0].value == 82.7
    assert out.cells["S1"].values[0].derivation is None


def test_creates_cell_for_college_sample_with_no_existing_cell():
    # The target field has NO cell for S1 (aggregation didn't resolve it); the
    # executor is source-driven and creates the cell.
    fields = {
        "Source of sample": Field(
            name="Source of sample",
            scope="sample",
            gender_specific=True,
            cells={"S1": Cell(values=[CellValue(value="college")])},
        ),
        TARGET: Field(name=TARGET, scope="sample", gender_specific=False, cells={}),
    }
    out = infer_college_sample_100(fields=fields, target=TARGET, skill=SKILL)
    assert out.cells["S1"].values[0].value == 100
    assert out.cells["S1"].values[0].derivation.kind == "infer_constant"
