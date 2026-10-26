"""Validate Bennett 2023 extraction outputs against Jansen d_long.xlsx.

Bennett is a QUALITATIVE meta-synthesis: the benchmark is 4 categorical
variables per included primary study — Country, Population, Type, Area.

Truth source:
  Jansen `d_long.xlsx` `meta == "Bennett2023"` slice, scored at (study x var)
  granularity: column `code` = gold answer, `llm_code_num` = correct?. This is
  the same file whose (model x var) aggregation reproduces Jansen's published
  per-model accuracy (see docs/reports/2026-06-18-bennett2023-benchmark-feasibility.md).

Two modes:
  --baseline   re-aggregate d_long to print Jansen's own per-model accuracy
               (harness self-check; needs NO extraction run).
  (default)    score our paper_target.json runs in data/runs/jansen_bennett2023/.

Scoring (after normalization):
  Country     — normalized single-string exact match (alias map: uk/america/...).
  Population  — set overlap vs the 5 canonical labels (Jaccard >= 0.5).
  Type        — set match (Primary/Secondary); near-degenerate -> kappa reported.
  Area        — set overlap (Risk/Recovery); 49/69 studies are BOTH.
Paper id (run-dir name) joins to the d_long study key by identity.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
D_LONG = JANSEN_DIR / "osfstorage-archive" / "Archive" / "analysis" / "d_long.xlsx"
RUNS_DEFAULT = run_dir("jansen_bennett2023")
VARS = ("Country", "Population", "Type", "Area")

# Jansen's published 8-model accuracy ranges (from d_long reproduction).
JANSEN_BASELINE = {
    "Country": (83.3, 94.4),
    "Population": (34.7, 64.6),
    "Type": (65.2, 82.2),
    "Area": (49.5, 71.2),
}

# ---------------------------------------------------------------- normalization
_COUNTRY_ALIAS = {
    "united kingdom": "uk", "u.k.": "uk", "great britain": "uk", "britain": "uk",
    "england": "uk", "scotland": "uk", "wales": "uk",
    "usa": "america", "u.s.": "america", "u.s.a.": "america", "us": "america",
    "united states": "america", "united states of america": "america", "the us": "america",
}


def norm_country(s: str) -> str:
    s = str(s).strip().lower().rstrip(".")
    return _COUNTRY_ALIAS.get(s, s)


def _canon_population(token: str) -> str | None:
    t = token.lower()
    if "ideation" in t and "attempt" not in t:
        return "suicidal ideation"
    if "bereav" in t:
        if "male" in t and "mixed" not in t:
            return "bereaved (male suicide)"
        return "bereaved (mixed)"
    if "attempt" in t:
        # men-only vs mixed
        if "(men)" in t or "(male)" in t or " men" in t or "male suicide" in t:
            return "attempted suicide (men)"
        return "attempted suicide (mixed)"
    return None


def norm_set(raw, kind: str) -> set[str]:
    """Tokenize a messy gold/extracted value into a canonical set."""
    out: set[str] = set()
    items: list[str] = []
    if isinstance(raw, (set, list, tuple)):
        items = [str(x) for x in raw]
    else:
        items = [str(raw)]
    for it in items:
        for tok in str(it).replace("|", ",").replace(";", ",").replace("/", ",").split(","):
            tok = tok.strip().lower()
            if not tok or tok in ("nan", "none", "no", ""):
                continue
            if kind == "Population":
                # split compound "+ ... + ..." too
                for part in tok.split("+"):
                    c = _canon_population(part.strip())
                    if c:
                        out.add(c)
            elif kind == "Type":
                if "primary" in tok:
                    out.add("primary")
                if "secondary" in tok:
                    out.add("secondary")
            elif kind == "Area":
                if "risk" in tok:
                    out.add("risk")
                if "recovery" in tok:
                    out.add("recovery")
            else:  # Country
                out.add(norm_country(tok))
    return out


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------- gold + extract
def load_d_long() -> pd.DataFrame:
    df = pd.read_excel(D_LONG)
    return df[df["meta"] == "Bennett2023"].copy()


def gold_set(d_long: pd.DataFrame, study: str, var: str, kind: str) -> set[str]:
    sub = d_long[(d_long["study"] == study) & (d_long["var"] == var)]
    return norm_set(list(sub["code"].dropna().astype(str).unique()), kind)


def extract_value(e: dict, field: str):
    v = e.get(field)
    if isinstance(v, dict):
        for cell in v.values():
            if isinstance(cell, list) and cell and cell[0] not in (None, "None", ""):
                return cell[0]
        return None
    if isinstance(v, str) and v.lower() in ("none", "null", ""):
        return None
    return v


def extract_set(e: dict, field: str) -> set[str]:
    v = e.get(field)
    out: set[str] = set()
    cells = v.values() if isinstance(v, dict) else ([v] if v is not None else [])
    for cell in cells:
        stack = [cell]
        while stack:
            x = stack.pop()
            if isinstance(x, (list, tuple, set)):
                stack.extend(x)
            elif x not in (None, "None", ""):
                out.add(str(x))
    return out


# ---------------------------------------------------------------- baseline mode
def run_baseline(d_long: pd.DataFrame) -> int:
    d_long = d_long.copy()
    d_long["correct"] = pd.to_numeric(d_long["llm_code_num"], errors="coerce")
    piv = d_long.pivot_table(index="model", columns="var", values="correct", aggfunc="mean") * 100
    print("Jansen per-model accuracy reproduced from d_long (harness self-check):\n")
    print(piv[list(VARS)].round(1).to_string())
    print("\nPublished ranges (should match):")
    for v in VARS:
        lo, hi = JANSEN_BASELINE[v]
        print(f"  {v:12s} {piv[v].min():.1f}-{piv[v].max():.1f}%  (published {lo}-{hi}%)")
    return 0


# ---------------------------------------------------------------- our-run mode
def run_scoring(d_long: pd.DataFrame, runs_dir: Path) -> int:
    gold_studies = set(d_long["study"].dropna().unique())
    papers = sorted(
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and (d / "paper_target.json").exists()
    ) if runs_dir.exists() else []

    if not papers:
        print(f"No paper_target.json runs found in {runs_dir} yet.")
        print(f"(gold ready for {len(gold_studies)} studies; staged PDFs awaiting Marker + extraction.)")
        print("\nRun `--baseline` to self-check the harness against Jansen's models.")
        return 0

    exact = {v: 0.0 for v in VARS}
    overlap = {v: 0.0 for v in VARS}
    jac = {v: 0.0 for v in VARS}
    overpred = {v: 0 for v in VARS}
    total = {v: 0 for v in VARS}
    print(f"Scoring {len(papers)} Bennett runs vs d_long gold "
          f"(mark = exact set match; over = over-predicted labels)\n")
    print(f"{'Study':16s} {'Country':>10s} {'Population':>22s} {'Type':>14s} {'Area':>16s}")
    print("-" * 86)

    for paper in papers:
        if paper not in gold_studies:
            print(f"{paper:16s} (no d_long truth — unscored)")
            continue
        e = json.loads((runs_dir / paper / "paper_target.json").read_text())
        cells = []
        for v in VARS:
            gold = gold_set(d_long, paper, v, v)
            ours = norm_set(extract_value(e, v) or "", v) if v == "Country" \
                else norm_set(extract_set(e, v), v)
            j = jaccard(ours, gold)
            exact[v] += int(ours == gold)
            overlap[v] += int(j >= 0.5)
            jac[v] += j
            if ours > gold:
                overpred[v] += 1
            total[v] += 1
            mark = "✓" if ours == gold else ("~" if j >= 0.5 else "✗")
            cells.append(f"{mark}{','.join(sorted(ours))[:8]}/{','.join(sorted(gold))[:8]}")
        print(f"{paper:16s} {cells[0]:>10s} {cells[1]:>22s} {cells[2]:>14s} {cells[3]:>16s}")

    print("\n" + "=" * 78)
    print("AGGREGATE PER-VARIABLE ACCURACY  (✓ exact / ~ partial-overlap≥0.5 / ✗ miss)")
    print("=" * 78)
    print(f"{'Var':12s} {'exact':>7s} {'overlap':>8s} {'meanJ':>6s} {'over-pred':>9s} {'Jansen 8-model':>16s}")
    for v in VARS:
        ex = exact[v] / total[v] * 100 if total[v] else 0
        ov = overlap[v] / total[v] * 100 if total[v] else 0
        mj = jac[v] / total[v] if total[v] else 0
        lo, hi = JANSEN_BASELINE[v]
        print(f"{v:12s} {ex:>6.1f}% {ov:>7.1f}% {mj:>6.2f} {overpred[v]:>7d}   {f'{lo}-{hi}%':>14s}")
    n = sum(total.values())
    print(f"{'OVERALL':12s} {sum(exact.values())/n*100:>6.1f}% {sum(overlap.values())/n*100:>7.1f}%")
    print("\nNote: multi-label fields (Population, Area) — strict 'exact' penalizes the "
          "agent's tendency to\nover-predict labels; 'overlap' credits any gold-label hit. "
          "Truth is between; both shown for honesty.")
    return 0


def main() -> int:
    if not D_LONG.exists():
        sys.exit(f"!! gold not found: {D_LONG}")
    d_long = load_d_long()
    args = sys.argv[1:]
    if "--baseline" in args:
        return run_baseline(d_long)
    runs = Path(next((a for a in args if not a.startswith("-")), RUNS_DEFAULT))
    return run_scoring(d_long, runs)


if __name__ == "__main__":
    raise SystemExit(main())
