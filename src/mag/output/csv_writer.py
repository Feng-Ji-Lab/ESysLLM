"""Tidy long-format CSV: one row per (paper, sample_key, field) with a JSON value."""

from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from mag.models import PaperResult

_FIELDNAMES = ["paper_id", "sample_key", "field", "value"]


def to_rows(paper: PaperResult) -> list[dict]:
    rows: list[dict] = []
    for name, field in paper.fields.items():
        if field.scope == "paper":
            value = field.paper_value.value if field.paper_value is not None else None
            rows.append(
                {
                    "paper_id": paper.paper_id,
                    "sample_key": "",
                    "field": name,
                    "value": json.dumps(value, ensure_ascii=False),
                }
            )
        else:
            for key, cell in field.cells.items():
                rows.append(
                    {
                        "paper_id": paper.paper_id,
                        "sample_key": key,
                        "field": name,
                        "value": json.dumps([cv.value for cv in cell.values], ensure_ascii=False),
                    }
                )
    return rows


def write_csv(paper: PaperResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        writer.writeheader()
        writer.writerows(to_rows(paper))
