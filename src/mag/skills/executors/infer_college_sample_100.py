"""Executor: a college sample implies 100% college-or-higher education."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mag.models import Cell, CellValue, Derivation

if TYPE_CHECKING:
    from mag.models import Field
    from mag.skills.loader import Skill


def infer_college_sample_100(
    *, fields: dict[str, Field], target: str, skill: Skill, context: dict | None = None
) -> Field:
    """Return a copy of fields[target] where college samples missing a value get 100.

    Source-driven: iterates the "Source of sample" cells (which define which samples
    are college), so it can CREATE a target cell for a college sample that
    aggregation never resolved a value for — not only fill an existing empty one.
    """
    field = fields[target]
    source = fields.get("Source of sample")
    new_cells: dict[str, Cell] = dict(field.cells)
    if source is not None:
        for key, src_cell in source.cells.items():
            is_college = bool(src_cell.values) and src_cell.values[0].value == "college"
            if not is_college:
                continue
            existing = new_cells.get(key)
            missing = existing is None or not existing.values or existing.values[0].value is None
            if missing:
                new_cells[key] = Cell(
                    values=[
                        CellValue(
                            value=100,
                            derivation=Derivation(
                                kind="infer_constant",
                                skill_name=skill.name,
                                inputs={"source_of_sample": "college"},
                                formula="college sample → 100% college-or-higher education",
                            ),
                        )
                    ]
                )
    return field.model_copy(update={"cells": new_cells})
