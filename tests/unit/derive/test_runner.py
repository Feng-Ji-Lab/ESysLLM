"""Tests for the Stage-3 derive runner."""

from __future__ import annotations

from pathlib import Path

from mag.derive.runner import run_derivations
from mag.models import Cell, CellValue, Field
from mag.skills.loader import load_skills

SKILLS = load_skills(Path("rules"))

FIELDS_CFG = {
    "fields": [
        {"name": "Source of sample", "scope": "sample", "gender_specific": True},
        {"name": "Sample", "scope": "sample", "gender_specific": True, "skills": ["total_geq_sum"]},
        {
            "name": "Percentage of college or higher of participants",
            "scope": "sample",
            "gender_specific": False,
            "skills": ["infer_college_sample_100"],
        },
        {
            "name": "Mean BMI of participants",
            "scope": "sample",
            "gender_specific": True,
            "skills": ["compute_weighted_mean_total"],
        },
    ]
}


def _fields():
    return {
        "Source of sample": Field(
            name="Source of sample",
            scope="sample",
            gender_specific=True,
            cells={"S1": Cell(values=[CellValue(value="college")])},
        ),
        "Sample": Field(
            name="Sample",
            scope="sample",
            gender_specific=True,
            cells={
                "S1": Cell(values=[CellValue(value=90), CellValue(value=50), CellValue(value=50)])
            },
        ),
        "Percentage of college or higher of participants": Field(
            name="Percentage of college or higher of participants",
            scope="sample",
            gender_specific=False,
            cells={"S1": Cell(values=[])},
        ),
        "Mean BMI of participants": Field(
            name="Mean BMI of participants",
            scope="sample",
            gender_specific=True,
            cells={
                "S1": Cell(
                    values=[CellValue(value=None), CellValue(value=24.0), CellValue(value=26.0)]
                )
            },
        ),
    }


def test_executors_run_then_validators():
    fields, warnings = run_derivations(fields=_fields(), fields_cfg=FIELDS_CFG, skills=SKILLS)
    # college → 100 inferred
    assert (
        fields["Percentage of college or higher of participants"].cells["S1"].values[0].value == 100
    )
    # weighted mean total = (24*50 + 26*50)/100 = 25.0
    assert fields["Mean BMI of participants"].cells["S1"].values[0].value == 25.0
    # total 90 < 50+50=100 → validator warns
    assert any(w.code == "total_lt_sum" for w in warnings)


def test_no_skills_is_noop():
    cfg = {"fields": [{"name": "Author", "scope": "paper"}]}
    fields = {"Author": Field(name="Author", scope="paper", paper_value=CellValue(value="X"))}
    out, warnings = run_derivations(fields=fields, fields_cfg=cfg, skills=SKILLS)
    assert out["Author"].paper_value.value == "X"
    assert warnings == []


def test_unknown_executor_name_raises():
    import pytest

    from mag.skills.loader import Skill

    skills = {"bad": Skill(name="bad", executor="does_not_exist")}
    cfg = {"fields": [{"name": "Sample", "scope": "sample", "skills": ["bad"]}]}
    fields = {"Sample": Field(name="Sample", scope="sample", cells={})}
    with pytest.raises(KeyError):
        run_derivations(fields=fields, fields_cfg=cfg, skills=skills)


def test_run_derivations_passes_context_to_executor():
    from mag.derive import runner
    from mag.models import Field
    from mag.skills.loader import Skill

    seen = {}

    def fake_exec(*, fields, target, skill, context=None):
        seen["context"] = context
        return fields[target]

    saved = runner.EXECUTORS.copy()
    runner.EXECUTORS["_probe"] = fake_exec
    try:
        fields = {"X": Field(name="X", scope="paper")}
        cfg = {"fields": [{"name": "X", "skills": ["_probe"]}]}
        skills = {"_probe": Skill(name="_probe", executor="_probe")}
        runner.run_derivations(fields=fields, fields_cfg=cfg, skills=skills, context={"k": 1})
        assert seen["context"] == {"k": 1}
    finally:
        runner.EXECUTORS.clear()
        runner.EXECUTORS.update(saved)
