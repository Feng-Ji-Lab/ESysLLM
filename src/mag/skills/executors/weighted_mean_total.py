"""Executor: fill a gender-specific field's total via the size-weighted mean."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mag.models import Cell, CellValue, Derivation

if TYPE_CHECKING:
    from mag.models import Field
    from mag.skills.loader import Skill


def _is_num(x: object) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def compute_weighted_mean_total(
    *, fields: dict[str, Field], target: str, skill: Skill, context: dict | None = None
) -> Field:
    """Return a copy of fields[target] with each cell's missing total computed as
    (mf*nf + mm*nm) / (nf+nm) from the Sample field's female/male counts."""
    field = fields[target]
    sample = fields.get("Sample")
    precision = int(skill.extras.get("precision", 4))

    new_cells: dict[str, Cell] = {}
    for key, cell in field.cells.items():
        vals = list(cell.values)
        counts = sample.cells.get(key) if sample else None
        if (
            len(vals) >= 3
            and vals[0].value is None
            and _is_num(vals[1].value)
            and _is_num(vals[2].value)
            and counts is not None
            and len(counts.values) >= 3
            and _is_num(counts.values[1].value)
            and _is_num(counts.values[2].value)
        ):
            mf, mm = vals[1].value, vals[2].value
            nf, nm = counts.values[1].value, counts.values[2].value
            if nf + nm:
                total = round((mf * nf + mm * nm) / (nf + nm), precision)
                vals[0] = CellValue(
                    value=total,
                    derivation=Derivation(
                        kind="weighted_mean",
                        skill_name=skill.name,
                        inputs={"female_mean": mf, "male_mean": mm, "female_n": nf, "male_n": nm},
                        formula=f"({mf}*{nf} + {mm}*{nm}) / {nf + nm}",
                    ),
                )
        new_cells[key] = Cell(values=vals)
    return field.model_copy(update={"cells": new_cells})
