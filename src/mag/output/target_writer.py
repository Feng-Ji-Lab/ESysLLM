"""Flatten a PaperResult into the user-facing target shape.

Paper-scope fields become top-level scalars; sample-scope fields become
{rendered_sample_key: [values]}. Every declared sample is shown; a field with no
cell for a sample — or a cell whose values are all None — renders as []. Field
and sample order follow the PaperResult's insertion order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mag.models import Cell, PaperResult


def _cell_values(cell: Cell | None) -> list:
    if cell is None:
        return []
    vals = [cv.value for cv in cell.values]
    if all(v is None for v in vals):  # empty list, or all-None → absent
        return []
    return vals


def to_target_dict(paper: PaperResult) -> dict[str, Any]:
    sample_keys = [s.rendered for s in paper.samples]
    out: dict[str, Any] = {}
    for name, field in paper.fields.items():
        if field.scope == "paper":
            out[name] = field.paper_value.value if field.paper_value is not None else None
        else:
            # Every declared sample is shown; extra cell keys not in paper.samples
            # are appended after (defensive).
            keys = sample_keys + [k for k in field.cells if k not in sample_keys]
            values_by_key = {key: _cell_values(field.cells.get(key)) for key in keys}
            if name == "Sample":
                # An all-one-gender sample reports the absent gender as a true
                # absence: normalize a 0 count to null for consistency.
                values_by_key = {
                    key: [None if v == 0 else v for v in vals]
                    for key, vals in values_by_key.items()
                }
            out[name] = values_by_key
    return out
