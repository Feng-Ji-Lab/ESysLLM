"""Tests for the weighted-mean-total executor (deterministic, no LLM)."""

from __future__ import annotations

from mag.models import Cell, CellValue, Field
from mag.skills.executors.weighted_mean_total import compute_weighted_mean_total
from mag.skills.loader import Skill

SKILL = Skill(
    name="compute_weighted_mean_total",
    executor="compute_weighted_mean_total",
    applies_to=["Mean BMI of participants"],
    extras={"precision": 4},
)


def _fields(total, female, male, nf, nm):
    sample = Field(
        name="Sample",
        scope="sample",
        gender_specific=True,
        cells={
            "S1": Cell(values=[CellValue(value=nf + nm), CellValue(value=nf), CellValue(value=nm)])
        },
    )
    bmi = Field(
        name="Mean BMI of participants",
        scope="sample",
        gender_specific=True,
        cells={
            "S1": Cell(
                values=[CellValue(value=total), CellValue(value=female), CellValue(value=male)]
            )
        },
    )
    return {"Sample": sample, "Mean BMI of participants": bmi}


def test_computes_weighted_mean_when_total_missing():
    fields = _fields(total=None, female=24.0, male=26.0, nf=367, nm=308)
    out = compute_weighted_mean_total(fields=fields, target="Mean BMI of participants", skill=SKILL)
    cell = out.cells["S1"]
    # (24*367 + 26*308) / 675 = 24.912592...
    assert cell.values[0].value == round((24.0 * 367 + 26.0 * 308) / 675, 4)
    assert cell.values[0].derivation is not None
    assert cell.values[0].derivation.kind == "weighted_mean"
    # female/male positions untouched
    assert cell.values[1].value == 24.0
    assert cell.values[2].value == 26.0


def test_leaves_existing_total_untouched():
    fields = _fields(total=25.0, female=24.0, male=26.0, nf=100, nm=100)
    out = compute_weighted_mean_total(fields=fields, target="Mean BMI of participants", skill=SKILL)
    assert out.cells["S1"].values[0].value == 25.0
    assert out.cells["S1"].values[0].derivation is None


def test_skips_when_counts_missing():
    # Sample has no gender counts → cannot weight → leave total None
    sample = Field(
        name="Sample",
        scope="sample",
        gender_specific=True,
        cells={"S1": Cell(values=[CellValue(value=675)])},
    )
    bmi = Field(
        name="Mean BMI of participants",
        scope="sample",
        gender_specific=True,
        cells={
            "S1": Cell(values=[CellValue(value=None), CellValue(value=24.0), CellValue(value=26.0)])
        },
    )
    out = compute_weighted_mean_total(
        fields={"Sample": sample, "Mean BMI of participants": bmi},
        target="Mean BMI of participants",
        skill=SKILL,
    )
    assert out.cells["S1"].values[0].value is None


def test_returns_new_field_does_not_mutate_input():
    fields = _fields(total=None, female=24.0, male=26.0, nf=1, nm=1)
    original = fields["Mean BMI of participants"]
    compute_weighted_mean_total(fields=fields, target="Mean BMI of participants", skill=SKILL)
    assert original.cells["S1"].values[0].value is None  # input untouched
