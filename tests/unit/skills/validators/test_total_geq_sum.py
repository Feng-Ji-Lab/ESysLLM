"""Tests for the total >= female+male validator."""

from __future__ import annotations

from mag.models import Cell, CellValue, Field
from mag.skills.loader import Skill
from mag.skills.validators.total_geq_sum import total_geq_sum

SKILL = Skill(name="total_geq_sum", validator="total_geq_sum", applies_to=["Sample"])


def _sample(total, female, male):
    return {
        "Sample": Field(
            name="Sample",
            scope="sample",
            gender_specific=True,
            cells={
                "S1": Cell(
                    values=[CellValue(value=total), CellValue(value=female), CellValue(value=male)]
                )
            },
        )
    }


def test_warns_when_total_lt_sum():
    warnings = total_geq_sum(fields=_sample(100, 60, 50), skill=SKILL)
    assert len(warnings) == 1
    assert warnings[0].code == "total_lt_sum"
    assert warnings[0].sample_key == "S1"


def test_no_warning_when_consistent():
    assert total_geq_sum(fields=_sample(110, 60, 50), skill=SKILL) == []


def test_no_warning_when_not_all_numeric():
    assert total_geq_sum(fields=_sample(None, 60, 50), skill=SKILL) == []


def test_no_sample_field_is_noop():
    assert total_geq_sum(fields={}, skill=SKILL) == []
