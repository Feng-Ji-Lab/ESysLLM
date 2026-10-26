"""single_gender_fill executor."""

from __future__ import annotations

from mag.models import Cell, CellValue, Field
from mag.skills.executors.single_gender_fill import single_gender_fill
from mag.skills.loader import Skill

SKILL = Skill(name="single_gender_fill", executor="single_gender_fill")


def _field(name, cells):
    return Field(
        name=name,
        scope="sample",
        gender_specific=True,
        cells={k: Cell(values=[CellValue(value=v) for v in vs]) for k, vs in cells.items()},
    )


def test_fills_female_slot_for_all_female_total_only():
    fields = {"Sample": _field("Sample", {"Study 1 - US": [8925]})}
    ctx = {"sample_gender": {"Study 1 - US": "all_female"}}
    out = single_gender_fill(fields=fields, target="Sample", skill=SKILL, context=ctx)
    assert [cv.value for cv in out.cells["Study 1 - US"].values] == [8925, 8925, None]


def test_fills_male_slot_for_all_male():
    fields = {"Sample": _field("Sample", {"Study 2 - men": [50]})}
    ctx = {"sample_gender": {"Study 2 - men": "all_male"}}
    out = single_gender_fill(fields=fields, target="Sample", skill=SKILL, context=ctx)
    assert [cv.value for cv in out.cells["Study 2 - men"].values] == [50, None, 50]


def test_does_not_overwrite_existing_breakdown():
    fields = {"Sample": _field("Sample", {"Study 1 - US": [100, 60, 40]})}
    ctx = {"sample_gender": {"Study 1 - US": "all_female"}}
    out = single_gender_fill(fields=fields, target="Sample", skill=SKILL, context=ctx)
    assert [cv.value for cv in out.cells["Study 1 - US"].values] == [100, 60, 40]


def test_noop_for_mixed_or_missing_gender():
    fields = {"Sample": _field("Sample", {"Study 1 - mix": [100]})}
    out = single_gender_fill(
        fields=fields, target="Sample", skill=SKILL, context={"sample_gender": {}}
    )
    assert [cv.value for cv in out.cells["Study 1 - mix"].values] == [100]


def test_marks_derivation_on_filled_slot():
    fields = {"Sample": _field("Sample", {"Study 1 - US": [8925]})}
    ctx = {"sample_gender": {"Study 1 - US": "all_female"}}
    out = single_gender_fill(fields=fields, target="Sample", skill=SKILL, context=ctx)
    deriv = out.cells["Study 1 - US"].values[1].derivation
    assert deriv is not None and deriv.kind == "infer_single_gender"


def test_noop_when_total_is_none():
    fields = {"Sample": _field("Sample", {"Study 1 - US": [None]})}
    ctx = {"sample_gender": {"Study 1 - US": "all_female"}}
    out = single_gender_fill(fields=fields, target="Sample", skill=SKILL, context=ctx)
    assert [cv.value for cv in out.cells["Study 1 - US"].values] == [None]


def test_fills_padded_all_female_cell():
    fields = {
        "Mean BMI of participants": _field(
            "Mean BMI of participants", {"Study 1 - US": [26.75, None, None]}
        )
    }
    ctx = {"sample_gender": {"Study 1 - US": "all_female"}}
    out = single_gender_fill(
        fields=fields, target="Mean BMI of participants", skill=SKILL, context=ctx
    )
    assert [cv.value for cv in out.cells["Study 1 - US"].values] == [26.75, 26.75, None]


def test_fills_padded_all_male_cell():
    fields = {"Sample": _field("Sample", {"Study 2 - men": [50, None, None]})}
    ctx = {"sample_gender": {"Study 2 - men": "all_male"}}
    out = single_gender_fill(fields=fields, target="Sample", skill=SKILL, context=ctx)
    assert [cv.value for cv in out.cells["Study 2 - men"].values] == [50, None, 50]


def test_does_not_overwrite_padded_cell_with_real_female():
    # female slot already has a real value → leave untouched even if male is None
    fields = {"Sample": _field("Sample", {"Study 1 - US": [100, 60, None]})}
    ctx = {"sample_gender": {"Study 1 - US": "all_female"}}
    out = single_gender_fill(fields=fields, target="Sample", skill=SKILL, context=ctx)
    assert [cv.value for cv in out.cells["Study 1 - US"].values] == [100, 60, None]
