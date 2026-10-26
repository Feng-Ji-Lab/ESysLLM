"""Score Bowes 2023 under the SAME CED/IED/MD standard as the Vu/Ng record.

Reuses `eval/_dashboard/common.py` classifiers and `build_dashboard._from_counts`
so the Strict / Widened metrics are computed by identical code paths.

Item = one (paper x field), micro-averaged — the same granularity as
docs/reports/2026-07-01-vu-ng-metrics-record.md.

  exact    - extraction fully matches the reference            -> CED (both)
  contains - reference appears within extraction, with extras  -> IED strict / CED widened
  wrong    - extraction present, reference not fully contained -> IED
  missing  - reference present, nothing extracted              -> MD

Field rules (mirroring Vu's multiset cells / Ng's set fields):
  YearOfPub  scalar, exact int
  COVID      scalar, exact category
  CTType     set of conspiracy-measure types
  Outcome    set of construct tokens (study-level union)
  SampleType multiset of recruitment categories across samples
  Females    multiset of female-% across samples, tol +/-1.0 pp
  outcome_es multiset of outcome tokens across effect sizes
  es_es      set of (outcome, es) pairs, es tol +/-0.015
  N_es       set of (outcome, N) pairs, N tol +/-2%

Usage:  PYTHONPATH=. python scripts/score_bowes_ced.py
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd

from eval._dashboard.build_dashboard import _from_counts
from eval._dashboard.common import classify_multiset, classify_scalar, classify_set

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
GS = REPO / "eval" / "bowes2023" / "gold_samplelevel.csv"
GE = REPO / "eval" / "bowes2023" / "gold_effectsizes.csv"
RUNS = run_dir("jansen_bowes2023")

FIELDS = ("YearOfPub", "CTType", "COVID", "Females", "SampleType",
          "Outcome", "outcome_es", "es_es", "N_es")
FEM_TOL = 1.0
ES_TOL = 0.015
N_TOL_FRAC = 0.02


def norm(s) -> str:
    return str(s).strip().lower().rstrip(".")


def _classify_tol_pairs(gold: list, ours: list, eq) -> str:
    """1:1 tolerance match. exact = all gold matched & no extras;
    contains = all gold matched with extras; missing = nothing extracted."""
    if not gold:
        raise ValueError("no gold")
    if not ours:
        return "missing"
    used = [False] * len(ours)
    matched = 0
    for g in gold:
        for i, o in enumerate(ours):
            if not used[i] and eq(g, o):
                used[i] = True
                matched += 1
                break
    if matched < len(gold):
        return "wrong"
    return "exact" if all(used) else "contains"


def evaluate(paper: str, field: str, e: dict, gsub: pd.DataFrame, ge_p: pd.DataFrame) -> str | None:
    """Return klass, or None when no reference exists (cell excluded)."""
    study = e.get("study", {}) or {}
    samples = e.get("samples", []) or []
    es_rows = e.get("effect_sizes", []) or []
    grow = gsub.iloc[0]

    if field == "YearOfPub":
        try:
            ours = int(float(study.get("YearOfPub")))
        except (TypeError, ValueError):
            return classify_scalar(False, False)
        return classify_scalar(ours == int(grow["YearOfPub"]), True)

    if field == "COVID":
        ours = study.get("COVID")
        return classify_scalar(bool(ours) and norm(ours) == norm(grow["COVID"]), bool(ours))

    if field == "CTType":
        ref = {norm(x) for x in gsub["CTType"].dropna().unique()}
        got = {norm(x) for x in (study.get("CTType") or [])}
        return classify_set(ref, got)

    if field == "Outcome":
        ref = {norm(t) for s in gsub["outcomes"].dropna() for t in str(s).split("|") if t}
        got = {norm(r.get("outcome")) for r in es_rows if r.get("outcome")}
        return classify_set(ref, got)

    if field == "SampleType":
        ref = Counter(norm(x) for x in gsub["SampleType"].dropna())
        if not ref:
            return None
        got = Counter(norm(s.get("recruitment")) for s in samples if s.get("recruitment"))
        return classify_multiset(ref, got)

    if field == "Females":
        ref = [float(x) for x in gsub["Females_pct"] if pd.notna(x)]
        if not ref:
            return None
        got = [float(s["female_pct"]) for s in samples
               if s.get("female_pct") is not None and not isinstance(s.get("female_pct"), str)]
        return _classify_tol_pairs(ref, got, lambda g, o: abs(g - o) <= FEM_TOL)

    # --- effect-size fields -------------------------------------------------
    if ge_p.empty:
        return None

    if field == "outcome_es":
        ref = Counter(norm(r.outcome) for r in ge_p.itertuples())
        got = Counter(norm(r.get("outcome")) for r in es_rows if r.get("outcome"))
        return classify_multiset(ref, got)

    def _ours_pairs():
        out = []
        for r in es_rows:
            try:
                out.append((norm(r.get("outcome")), float(r.get("es")), r.get("N")))
            except (TypeError, ValueError):
                pass
        return out

    if field == "es_es":
        ref = [(norm(r.outcome), float(r.es)) for r in ge_p.itertuples()]
        got = _ours_pairs()
        return _classify_tol_pairs(
            ref, got, lambda g, o: g[0] == o[0] and abs(g[1] - o[1]) <= ES_TOL)

    if field == "N_es":
        ref = [(norm(r.outcome), float(r.N)) for r in ge_p.itertuples() if pd.notna(r.N)]
        if not ref:
            return None
        got = [(o, es, n) for (o, es, n) in _ours_pairs() if n is not None]

        def eq(g, o):
            try:
                return g[0] == o[0] and abs(float(o[2]) - g[1]) <= max(2.0, N_TOL_FRAC * g[1])
            except (TypeError, ValueError):
                return False
        return _classify_tol_pairs(ref, got, eq)

    raise KeyError(field)


def main() -> int:
    gs = pd.read_csv(GS)
    ge = pd.read_csv(GE)
    papers = sorted(p for p in gs.paper_id.unique() if (RUNS / p / "extraction.json").exists())

    counts = {f: {"exact": 0, "contains": 0, "wrong": 0, "missing": 0} for f in FIELDS}
    for p in papers:
        e = json.loads((RUNS / p / "extraction.json").read_text())
        gsub = gs[gs.paper_id == p]
        ge_p = ge[ge.paper_id == p]
        for f in FIELDS:
            k = evaluate(p, f, e, gsub, ge_p)
            if k is not None:
                counts[f][k] += 1

    print(f"Bowes 2023 — CED/IED/MD (same standard as Vu/Ng record) — {len(papers)} papers\n")
    print("Classification counts:")
    print(f"{'Field':12s}{'exact':>7s}{'contains':>10s}{'wrong':>7s}{'missing':>9s}{'scored':>8s}")
    for f in FIELDS:
        c = counts[f]
        print(f"{f:12s}{c['exact']:>7d}{c['contains']:>10d}{c['wrong']:>7d}"
              f"{c['missing']:>9d}{sum(c.values()):>8d}")

    tot = {k: sum(counts[f][k] for f in FIELDS) for k in ("exact", "contains", "wrong", "missing")}
    for std in ("strict", "widened"):
        print(f"\n{std.capitalize()}:")
        print(f"{'Field':12s}{'CED':>5s}{'IED':>5s}{'MD':>4s}"
              f"{'Prec':>8s}{'Recall':>8s}{'F1':>8s}{'Acc':>8s}")
        for f in FIELDS:
            m = _from_counts(counts[f], std)
            print(f"{f:12s}{m['ced']:>5d}{m['ied']:>5d}{m['md']:>4d}"
                  f"{m['precision']:>8.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}{m['accuracy']:>8.3f}")
        m = _from_counts(tot, std)
        print(f"{'OVERALL':12s}{m['ced']:>5d}{m['ied']:>5d}{m['md']:>4d}"
              f"{m['precision']:>8.3f}{m['recall']:>8.3f}{m['f1']:>8.3f}{m['accuracy']:>8.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
