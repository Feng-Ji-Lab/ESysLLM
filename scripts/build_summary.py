"""Recompute every number the paper reports from results/*/scored_cells.csv and
check it against results/paper_numbers.yaml; write results/summary.csv.

Each yaml entry says where the number appears in the manuscript, how to select the
cells (ma, study, model, temperature, field, paper subset), which standard applies
(coverage = exact+contains count as correct — the paper's rule; strict = exact only)
and which metric (precision | recall | f1 | accuracy | n_papers | n_items). Entries whose
value comes from re-scoring Jansen et al. (2025)'s released codings instead point at
the scorer script and the output line to read (``source: script``), because those
codings are not part of scored_cells.csv.

Exit status is 1 if any entry with a ``paper_value`` differs from the recomputed value
by more than ``tolerance`` (default 0.0005) and carries no ``note``. Entries with a
``note`` are reported, never fatal — that is how the known text-vs-data discrepancies
are kept visible (see docs/known_discrepancies.md).

Usage:  PYTHONPATH=.:src python scripts/build_summary.py [--no-scripts]
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from eval._paths import RESULTS_DIR  # noqa: E402

NUMBERS = RESULTS_DIR / "paper_numbers.yaml"
OUT = RESULTS_DIR / "summary.csv"
TOL = 0.0005
FLOAT = re.compile(r"-?\d+\.\d+")


def load_cells() -> list[dict]:
    rows: list[dict] = []
    for f in sorted(RESULTS_DIR.glob("*/scored_cells.csv")):
        with f.open(encoding="utf-8") as fh:
            rows.extend(csv.DictReader(fh))
    return rows


def select(rows: list[dict], sel: dict) -> list[dict]:
    out = rows
    for key in ("ma", "study", "model", "temperature", "field", "pipeline"):
        if key in sel:
            want = sel[key] if isinstance(sel[key], list) else [sel[key]]
            out = [r for r in out if r[key] in {str(w) for w in want}]
    if "papers" in sel:
        out = [r for r in out if r["paper_id"] in set(sel["papers"])]
    if "papers_exclude" in sel:
        out = [r for r in out if r["paper_id"] not in set(sel["papers_exclude"])]
    return out


def metrics(rows: list[dict], standard: str) -> dict:
    col = "correct_coverage" if standard == "coverage" else "correct_strict"
    ced = sum(int(r[col]) for r in rows)
    md = sum(r["match_class"] == "missing" for r in rows)
    ied = len(rows) - ced - md
    p = ced / (ced + ied) if ced + ied else 0.0
    rc = ced / (ced + md) if ced + md else 0.0
    f1 = 2 * p * rc / (p + rc) if p + rc else 0.0
    return {"precision": p, "recall": rc, "f1": f1,
            "accuracy": ced / len(rows) if rows else 0.0,
            "n_items": len(rows), "n_papers": len({r["paper_id"] for r in rows}),
            "ced": ced, "ied": ied, "md": md}


_SCRIPT_CACHE: dict[str, str] = {}


def run_script(name: str) -> str:
    if name not in _SCRIPT_CACHE:
        env = {"PYTHONPATH": f"{REPO}:{REPO / 'src'}"}
        import os

        env = {**os.environ, **env}
        res = subprocess.run([sys.executable, str(REPO / "scripts" / name)], cwd=REPO, env=env,
                             capture_output=True, text=True, check=True)
        _SCRIPT_CACHE[name] = res.stdout
    return _SCRIPT_CACHE[name]


def from_script(src: dict) -> float:
    text = run_script(src["script"])
    if src.get("section"):
        parts = re.split(r"^=== ", text, flags=re.M)
        text = next(p for p in parts if p.startswith(src["section"]))
    if src.get("after"):
        text = text.split(src["after"], 1)[1]
    line = next(ln for ln in text.splitlines() if ln.strip().startswith(src["line"]))
    return float(FLOAT.findall(line)[src.get("index", 0)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-scripts", action="store_true", help="skip entries sourced from scorer scripts")
    ap.add_argument("--tolerance", type=float, default=TOL)
    args = ap.parse_args()

    rows = load_cells()
    entries = yaml.safe_load(NUMBERS.read_text(encoding="utf-8"))
    out, failures = [], 0
    computed: dict[str, float] = {}
    for e in entries:
        rec = {"id": e["id"], "paper_location": e["location"], "ma": e.get("ma", ""),
               "metric": e["metric"], "standard": e.get("standard", ""),
               "paper_value": e.get("paper_value", ""), "computed_value": "", "n_papers": "",
               "n_items": "", "scorer": e.get("scorer", ""), "status": "", "note": e.get("note", "")}
        try:
            if "source" in e:
                if args.no_scripts:
                    rec["status"] = "skipped"
                    out.append(rec)
                    continue
                val = from_script(e["source"])
                rec["scorer"] = rec["scorer"] or f"scripts/{e['source']['script']}"
            elif "derived" in e:
                d = e["derived"]
                val = computed[d["a"]] - computed[d["b"]]
            else:
                sel = dict(e["select"])
                if e.get("ma"):  # entry-level ma always restricts the selection
                    sel.setdefault("ma", e["ma"])
                sub = select(rows, sel)
                m = metrics(sub, e.get("standard", "coverage"))
                val = m[e["metric"]]
                rec["n_papers"], rec["n_items"] = m["n_papers"], m["n_items"]
                rec["scorer"] = rec["scorer"] or sorted({r["scorer"] for r in sub})[0] if sub else ""
        except Exception as ex:  # noqa: BLE001 — report, keep going
            rec["status"] = f"error: {type(ex).__name__}: {ex}"
            failures += 1
            out.append(rec)
            continue
        computed[e["id"]] = val
        rec["computed_value"] = f"{val:.4f}" if isinstance(val, float) else val
        pv = e.get("paper_value")
        if pv is None:
            rec["status"] = "info"
        elif abs(float(pv) - float(val)) <= args.tolerance:
            rec["status"] = "match"
        elif e.get("note"):
            rec["status"] = "mismatch (documented)"
        else:
            rec["status"] = "MISMATCH"
            failures += 1
        out.append(rec)

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    width = max(len(r["id"]) for r in out)
    for r in out:
        print(f"{r['id']:{width}s}  paper={str(r['paper_value']):7s} computed={str(r['computed_value']):7s}  {r['status']}")
    print(f"\n{len(out)} entries, {failures} failure(s) -> {OUT.relative_to(REPO)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
