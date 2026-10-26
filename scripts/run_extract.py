"""Single-paper Stage 0+1+2+3 driver on a Marker drop-in dir (real Vertex Gemini).

Usage:
    source /projects/envs/miniconda3/etc/profile.d/conda.sh && conda activate research
    python scripts/run_extract.py --paper-id "<id>" \
        --marker-dir data/runs/<batch>/marker/<id> --out-dir data/runs/<batch>/<id>
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from mag.orchestrator import run_full
from mag.output.writers import write_outputs
from mag.prompts.loader import load_prompts
from mag.providers.gemini import GeminiProvider
from mag.settings import Settings
from mag.skills.loader import load_skills

REPO = Path(__file__).resolve().parent.parent


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--paper-id", required=True)
    ap.add_argument("--marker-dir", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--schema", default="bas-bmi")
    return ap


def extract_one(*, paper_id: str, marker_dir: Path, out_dir: Path, schema: str):
    """Run the full pipeline for one paper and write outputs. Returns the PaperResult."""
    s = Settings()
    s.schema_name = schema
    fields_cfg = json.loads((REPO / "schemas" / schema / "fields.json").read_text())
    prompts = load_prompts(REPO / "schemas" / schema)
    skills = list(load_skills(REPO / "rules").values())
    provider = GeminiProvider.from_settings(s)
    pr = run_full(
        provider=provider,
        marker_dir=marker_dir,
        paper_id=paper_id,
        pdf_path=f"{paper_id}.pdf",
        fields_cfg=fields_cfg,
        skills=skills,
        out_dir=out_dir,
        schema_name=schema,
        schema_version=fields_cfg.get("version", 2),
        started_at=datetime.now(UTC),
        prompts=prompts,
    )
    write_outputs(pr, out_dir)
    return pr


def main() -> int:
    a = build_arg_parser().parse_args()
    pr = extract_one(
        paper_id=a.paper_id, marker_dir=a.marker_dir, out_dir=a.out_dir, schema=a.schema
    )
    print("samples:", [sk.rendered for sk in pr.samples])
    print("warnings:", [w.code for w in pr.warnings])
    print(f"tokens: prompt={pr.run_meta.prompt_tokens} completion={pr.run_meta.completion_tokens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
