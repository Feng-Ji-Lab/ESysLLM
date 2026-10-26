"""Score an extracted paper_target.json against a target fixture.

Usage:
    python scripts/compare_extraction.py --extracted data/runs/.../paper_target.json \
        --target tests/fixtures/target_values/1Tylka2015.json [--out report.md] [--tol 0.05]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a plain script (no install) by adding src/ to the path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mag.scoring.compare import score


def build_report(
    extracted: dict,
    target: dict,
    *,
    tol: float,
    field_tol: dict[str, float] | None = None,
) -> str:
    rep = score(extracted, target, tol=tol, field_tol=field_tol)
    lines = [
        "# Extraction vs Target — Score Report",
        "",
        f"Tolerance: {tol}",
        "",
        "| Field | correct | incorrect | missing |",
        "|-------|---------|-----------|---------|",
    ]
    for field, m in rep["per_field"].items():
        lines.append(f"| {field} | {m['correct']} | {m['incorrect']} | {m['missing']} |")
    t = rep["totals"]
    lines += [
        "",
        f"**Totals:** correct={t['correct']} incorrect={t['incorrect']} missing={t['missing']}",
        "",
        f"**precision={t['precision']:.3f}  recall={t['recall']:.3f}  f1={t['f1']:.3f}**",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extracted", required=True, type=Path)
    ap.add_argument("--target", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--tol", type=float, default=0.05)
    args = ap.parse_args()

    extracted = json.loads(args.extracted.read_text(encoding="utf-8"))
    target = json.loads(args.target.read_text(encoding="utf-8"))
    md = build_report(extracted, target, tol=args.tol)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
