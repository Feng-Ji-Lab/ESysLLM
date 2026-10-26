"""Write the three Stage-4 artifacts for one paper."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mag.output.csv_writer import write_csv
from mag.output.target_writer import to_target_dict

if TYPE_CHECKING:
    from pathlib import Path

    from mag.models import PaperResult


def write_outputs(paper: PaperResult, out_dir: Path) -> dict[str, Path]:
    """Write paper_rich.json, paper_target.json, paper.csv; return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rich = out_dir / "paper_rich.json"
    target = out_dir / "paper_target.json"
    csv_path = out_dir / "paper.csv"

    rich.write_text(paper.model_dump_json(indent=2), encoding="utf-8")
    target.write_text(
        json.dumps(to_target_dict(paper), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_csv(paper, csv_path)
    return {"rich": rich, "target": target, "csv": csv_path}
