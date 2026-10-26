"""Executor: fill the gendered slot for a single-gender sample reported as a total only.

For a gender-specific field whose cell holds only [total] on a sample the census
marked "all_female"/"all_male", expand to [total, total, null] / [total, null, total].
Never overwrites an existing female/male breakdown (length-3 cell)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mag.models import Cell, CellValue, Derivation

if TYPE_CHECKING:
    from mag.models import Field
    from mag.skills.loader import Skill


def single_gender_fill(
    *, fields: dict[str, Field], target: str, skill: Skill, context: dict | None = None
) -> Field:
    field = fields[target]
    gender_by_key = (context or {}).get("sample_gender", {})
    new_cells: dict[str, Cell] = dict(field.cells)
    for key, cell in field.cells.items():
        gender = gender_by_key.get(key)
        if gender not in ("all_female", "all_male"):
            continue
        if not cell.values:
            continue
        total = cell.values[0].value
        if total is None:
            continue
        female_present = len(cell.values) >= 2 and cell.values[1].value is not None
        male_present = len(cell.values) >= 3 and cell.values[2].value is not None
        if female_present or male_present:
            continue  # a real breakdown already exists; never overwrite it
        filled = CellValue(
            value=total,
            derivation=Derivation(
                kind="infer_single_gender",
                skill_name=skill.name,
                inputs={"gender": gender, "total": total},
                formula=f"{gender} sample -> set "
                f"{'female' if gender == 'all_female' else 'male'} = total",
            ),
        )
        if gender == "all_female":
            values = [cell.values[0], filled, CellValue(value=None)]
        else:
            values = [cell.values[0], CellValue(value=None), filled]
        new_cells[key] = Cell(values=values)
    return field.model_copy(update={"cells": new_cells})
