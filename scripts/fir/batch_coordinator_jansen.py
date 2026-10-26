"""Rolling-batch Marker coordinator for the Jansen 2025 benchmark PDFs.

Adapted from the body-appreciation pipeline's `batch_coordinator.py` on Fir.

Differences from the original:
  * Takes --bench {hien2024|ng2023|vu2024} so each SLURM job processes one
    benchmark and finishes inside the 2:59h wall-clock limit.
  * Only runs the with-LLM pass (--use-llm). The body-appreciation pipeline
    ran both with/without to compare; for the Jansen reviewer-response we
    only need the best-quality extraction.
  * Skip-existing: if `<stem>.json` already exists in the output dir we don't
    re-process. This lets a timed-out job be resubmitted and resume.
  * Per-bench output: `output_jansen_benchmark/<bench>/<stem>/...`
  * Source: `PDF/jansen_benchmark/<bench>/*.pdf`

Run from `~/projects/def-fji/nanyuluo/meta_analysis/` on Fir:

    python scripts/batch_coordinator_jansen.py --bench hien2024
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List

BATCH_SIZE = 3

BENCH_CHOICES = ("hien2024", "ng2023", "vu2024", "bennett2023", "bowes2023", "buecker2023")


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_conversion(batch_files: List[Path],
                   batch_idx: int,
                   total_batches: int,
                   bench: str,
                   pdf_src_root: Path,
                   output_root: Path,
                   temp_dir: Path,
                   conversion_dir: Path) -> bool:
    """Copy `batch_files` into `temp_dir`, run run_workflow_v2.py once
    (with-LLM), verify every JSON exists. Returns True on success."""
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    log(f"[Batch {batch_idx}/{total_batches}] staging {len(batch_files)} PDFs")
    for pdf in batch_files:
        shutil.copy(pdf, temp_dir / pdf.name)

    abs_temp = temp_dir.resolve()
    abs_out = output_root.resolve()
    cwd = conversion_dir.resolve()

    log(f"[Batch {batch_idx}/{total_batches}] running Marker (Vertex AI) with --use-llm")
    cmd = [
        "python", "run_workflow_v2_vertex.py",
        "--pdf-dir", str(abs_temp),
        "--device", "cuda",
        "--use-llm",
        "-o", str(abs_out),
    ]
    try:
        subprocess.run(cmd, check=True, cwd=str(cwd))
    except subprocess.CalledProcessError as exc:
        log(f"!!! [Batch {batch_idx}] Marker exited non-zero: {exc}")
        return False

    # Verify
    all_ok = True
    for pdf in batch_files:
        stem = pdf.stem
        out_json = output_root / stem / f"{stem}.json"
        if not out_json.exists():
            log(f"  ✗ MISSING JSON for {stem}")
            all_ok = False
        else:
            size_kb = out_json.stat().st_size // 1024
            log(f"  ✓ {stem}.json ({size_kb} KB)")
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True, choices=BENCH_CHOICES)
    parser.add_argument(
        "--pdf-root",
        default="PDF/jansen_benchmark",
        type=Path,
        help="root containing one subdir per bench (default: PDF/jansen_benchmark)",
    )
    parser.add_argument(
        "--output-root",
        default="output_jansen_benchmark",
        type=Path,
        help="root for outputs; per-bench subdirs are created underneath",
    )
    parser.add_argument(
        "--conversion-dir",
        default="format_conversion",
        type=Path,
        help="directory containing run_workflow_v2.py (default: format_conversion)",
    )
    parser.add_argument(
        "--temp-dir",
        default=None,
        type=Path,
        help="staging directory for each batch (default: temp_jansen_<bench>)",
    )
    args = parser.parse_args()

    pdf_dir = args.pdf_root / args.bench
    output_dir = args.output_root / args.bench
    temp_dir = args.temp_dir or Path(f"temp_jansen_{args.bench}")
    conversion_dir = args.conversion_dir

    if not pdf_dir.exists():
        log(f"!!! PDF directory not found: {pdf_dir}")
        sys.exit(1)
    if not conversion_dir.exists():
        log(f"!!! Conversion script directory not found: {conversion_dir}")
        sys.exit(1)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_pdfs = sorted(pdf_dir.glob("*.pdf"))
    log(f"Bench: {args.bench}")
    log(f"PDFs found in {pdf_dir}: {len(all_pdfs)}")

    # Skip already-done
    todo: List[Path] = []
    for pdf in all_pdfs:
        out_json = output_dir / pdf.stem / f"{pdf.stem}.json"
        if out_json.exists() and out_json.stat().st_size > 1024:
            log(f"  skip (already done): {pdf.name}")
        else:
            todo.append(pdf)
    log(f"To process: {len(todo)} / {len(all_pdfs)}")

    if not todo:
        log("Nothing to do. Exiting cleanly.")
        return

    total_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE
    failures: List[str] = []

    for i in range(total_batches):
        batch_files = todo[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        batch_idx = i + 1
        log("=" * 60)
        log(f"BATCH {batch_idx}/{total_batches}")
        for f in batch_files:
            log(f"  - {f.name}")
        ok = run_conversion(
            batch_files=batch_files,
            batch_idx=batch_idx,
            total_batches=total_batches,
            bench=args.bench,
            pdf_src_root=pdf_dir,
            output_root=output_dir,
            temp_dir=temp_dir,
            conversion_dir=conversion_dir,
        )
        if not ok:
            failures.append(f"batch {batch_idx}: {[f.name for f in batch_files]}")
            # Don't abort entire job on one bad batch — note it and continue.
            # The next sbatch invocation will retry these via skip-existing.

    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    log("=" * 60)
    log(f"Done. Processed {len(todo)} PDFs in {total_batches} batches.")
    if failures:
        log(f"Failures ({len(failures)}):")
        for f in failures:
            log(f"  - {f}")
        sys.exit(2)
    log("All batches succeeded.")


if __name__ == "__main__":
    main()
