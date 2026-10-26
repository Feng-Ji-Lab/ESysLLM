"""Batch extraction driver for the Jansen 2025 benchmark replications.

Runs Stage 0+1+2 extraction over all Marker-processed PDFs in a bench. Idempotent:
already-completed papers are skipped; a Vertex 429 partway through doesn't
discard prior progress.

Usage:
    source /projects/envs/miniconda3/etc/profile.d/conda.sh && conda activate research
    python scripts/run_jansen_bench.py --bench vu2024
    python scripts/run_jansen_bench.py --bench vu2024 --only Dana2007 Bartling2014
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from mag.orchestrator import run_full
from mag.output.writers import write_outputs
from mag.prompts.loader import load_prompts
from mag.providers.gemini import GeminiProvider
from mag.settings import Settings
from mag.skills.loader import load_skills

REPO = Path(__file__).resolve().parent.parent
BENCH_TO_SCHEMA = {"vu2024": "vu2024", "ng2023": "ng2023", "hien2024": "hien2024",
                   "bennett2023": "bennett2023", "bowes2023": "bowes2023",
                   "buecker2023": "buecker2023"}


def discover_papers(bench: str, only: list[str] | None) -> list[Path]:
    """Find all Marker-output dirs under data/processed/<bench>/."""
    bench_dir = REPO / "data" / "processed" / bench
    if not bench_dir.is_dir():
        sys.exit(f"!! marker dir not found: {bench_dir}")
    papers = sorted(d for d in bench_dir.iterdir() if d.is_dir() and (d / f"{d.name}.json").exists())
    if only:
        papers = [d for d in papers if d.name in only]
    return papers


def run_one(*, paper_dir: Path, bench: str, out_root: Path, provider: GeminiProvider,
            fields_cfg: dict, skills: list, prompts) -> dict:
    paper_id = paper_dir.name
    out_dir = out_root / paper_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Idempotent skip: if final paper_target.json exists and is non-empty
    final = out_dir / "paper_target.json"
    if final.exists() and final.stat().st_size > 100:
        return {"paper_id": paper_id, "status": "skipped", "reason": "already done"}

    started = datetime.now(UTC)
    try:
        pr = run_full(
            provider=provider,
            marker_dir=paper_dir,
            paper_id=paper_id,
            pdf_path=f"{paper_id}.pdf",
            fields_cfg=fields_cfg,
            skills=skills,
            out_dir=out_dir,
            schema_name=bench,
            schema_version=fields_cfg.get("version", 1),
            started_at=started,
            prompts=prompts,
        )
        write_outputs(pr, out_dir)
        return {
            "paper_id": paper_id, "status": "ok",
            "elapsed_s": (datetime.now(UTC) - started).total_seconds(),
            "samples": [s.rendered for s in pr.samples],
            "n_warnings": len(pr.warnings),
            "prompt_tokens": pr.run_meta.prompt_tokens,
            "completion_tokens": pr.run_meta.completion_tokens,
        }
    except Exception as exc:
        return {
            "paper_id": paper_id, "status": "error",
            "error": f"{type(exc).__name__}: {exc!s}"[:300],
            "elapsed_s": (datetime.now(UTC) - started).total_seconds(),
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bench", required=True, choices=list(BENCH_TO_SCHEMA))
    ap.add_argument("--only", nargs="*", help="restrict to these paper ids (filenames without .pdf)")
    ap.add_argument("--out-root", type=Path,
                    default=None, help="default: data/runs/jansen_<bench>")
    ap.add_argument("--sleep-between", type=int, default=10,
                    help="seconds to sleep between papers (reduces 429 burst)")
    args = ap.parse_args()

    schema = BENCH_TO_SCHEMA[args.bench]
    out_root = args.out_root or (REPO / "data" / "runs" / f"jansen_{args.bench}")
    out_root.mkdir(parents=True, exist_ok=True)

    papers = discover_papers(args.bench, args.only)
    if not papers:
        sys.exit("!! no papers found")
    print(f"Discovered {len(papers)} papers in {args.bench}")

    s = Settings(); s.schema_name = schema
    fields_cfg = json.loads((REPO / "schemas" / schema / "fields.json").read_text())
    prompts = load_prompts(REPO / "schemas" / schema)
    skills = list(load_skills(REPO / "rules").values())
    provider = GeminiProvider.from_settings(s)

    results: list[dict] = []
    summary_path = out_root / "batch_summary.json"
    for i, paper_dir in enumerate(papers, 1):
        print(f"\n[{i}/{len(papers)}] {paper_dir.name}")
        r = run_one(paper_dir=paper_dir, bench=args.bench, out_root=out_root,
                    provider=provider, fields_cfg=fields_cfg, skills=skills, prompts=prompts)
        status = r["status"]
        if status == "ok":
            print(f"  ✓ {r['elapsed_s']:.0f}s | samples={len(r['samples'])} | "
                  f"warnings={r['n_warnings']} | tokens={r['prompt_tokens']}p+{r['completion_tokens']}c")
        elif status == "skipped":
            print(f"  ↷ {r['reason']}")
        else:
            print(f"  ✗ {r['error']}")
        results.append(r)
        summary_path.write_text(json.dumps(results, indent=2))
        if status == "ok" and i < len(papers):
            time.sleep(args.sleep_between)

    n_ok = sum(1 for r in results if r["status"] == "ok")
    n_skip = sum(1 for r in results if r["status"] == "skipped")
    n_err = sum(1 for r in results if r["status"] == "error")
    print(f"\nDone. ok={n_ok} skipped={n_skip} error={n_err} / {len(results)}")
    print(f"Summary: {summary_path}")
    return 0 if n_err == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
