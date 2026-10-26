"""Validator: a Sample's total must be >= female + male."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mag.models import Warning

if TYPE_CHECKING:
    from mag.models import Field
    from mag.skills.loader import Skill


def _is_num(x: object) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def total_geq_sum(*, fields: dict[str, Field], skill: Skill) -> list[Warning]:
    field = fields.get("Sample")
    if field is None:
        return []
    out: list[Warning] = []
    for key, cell in field.cells.items():
        vals = cell.values
        if len(vals) >= 3 and all(_is_num(v.value) for v in vals[:3]):
            total, female, male = vals[0].value, vals[1].value, vals[2].value
            if total < female + male:
                out.append(
                    Warning(
                        code="total_lt_sum",
                        message=f"total {total} < female+male {female + male}",
                        field_name="Sample",
                        sample_key=key,
                    )
                )
    return out
