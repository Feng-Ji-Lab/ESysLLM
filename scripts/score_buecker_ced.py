"""Score Buecker 2023 under the SAME CED/IED/MD standard as the Vu/Ng/Bennett/Bowes record.

Reuses `eval/_dashboard/common.py` classifiers and `build_dashboard._from_counts`
so the Strict / Widened metrics are computed by identical code paths.

Item = one (paper x field), micro-averaged — the same granularity as
docs/reports/2026-07-01-cross-ma-coverage-match-record.md §2.

  exact    - extraction fully matches the reference            -> CED (both)
  contains - reference appears within extraction, with extras  -> IED strict / CED widened
  wrong    - extraction present, reference not fully contained -> IED
  missing  - reference present, nothing extracted              -> MD

Scored fields = the 6 study-level descriptors Jansen (2025) benchmarked.
Five are scalars (no "contains" state is reachable), one is a set:

  yearT1            scalar int, tol +/-1        (gold's own coding tolerance)
  country           scalar, normalized string   (US/USA, UK/United Kingdom aliases)
  Outcome_variable  SET of SWB components       (life satisfaction / positive / negative affect)
  sample_type       scalar enum
  ethnicity         scalar enum
  lag               scalar float, tol +/-0.34   (years between waves)

Cells whose gold value is absent are excluded (unscored), matching the Bowes rule.
The per-record N/M/SD payload is NOT scored here — Jansen never benchmarked it; it is
reported separately (see the Buecker report), as with Bowes' per-effect-size recall.

Usage:  PYTHONPATH=src python scripts/score_buecker_ced.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
sys.path.insert(0, str(REPO / "scripts"))

from eval._dashboard.build_dashboard import _from_counts  # noqa: E402
from eval._dashboard.common import classify_scalar, classify_set  # noqa: E402
from validate_buecker_vs_jansen import STUDIES, gnum, load_gold_descriptors, norm  # noqa: E402

RUNS = run_dir("jansen_buecker2023_v6")
FIELDS = ("yearT1", "country", "Outcome_variable", "sample_type", "ethnicity", "lag")
YEAR_TOL = 1.0
LAG_TOL = 0.34


def _extracted(study: str) -> dict | None:
    p = RUNS / study / "paper_target.json"
    return json.loads(p.read_text()) if p.exists() else None


def _outcome_set(v) -> set:
    """Outcome_variable is emitted as a comma-separated string ("life satisfaction,
    positive affect") or a list; normalize either into a set of component tokens."""
    if v is None:
        return set()
    if isinstance(v, str):
        v = v.split(",")
    out = set()
    for x in v:
        if x in (None, "None", ""):
            continue
        n = norm(str(x))
        if n:
            out.add(n)
    return out


def classify_cell(field: str, gold, ext) -> str | None:
    """Return exact/contains/wrong/missing, or None when there is no reference."""
    if field == "Outcome_variable":
        ref = {norm(x) for x in gold} if gold else set()
        if not ref:
            return None
        return classify_set(ref, _outcome_set(ext))

    if gold is None or (isinstance(gold, str) and not gold.strip()):
        return None  # no reference -> unscored

    present = ext not in (None, "None", "")
    if field in ("yearT1", "lag"):
        tol = YEAR_TOL if field == "yearT1" else LAG_TOL
        g, e = gnum(gold), gnum(ext)
        if g is None:
            return None
        matched = e is not None and abs(e - g) <= tol
        return classify_scalar(matched, present and e is not None)

    return classify_scalar(norm(str(ext)) == norm(str(gold)), present)


def main() -> int:
    gold = load_gold_descriptors()
    counts = {f: {"exact": 0, "contains": 0, "wrong": 0, "missing": 0} for f in FIELDS}
    n_papers = 0
    for st in STUDIES:
        ext = _extracted(st)
        if ext is None or st not in gold:
            continue
        n_papers += 1
        for f in FIELDS:
            k = classify_cell(f, gold[st].get(f), ext.get(f))
            if k is not None:
                counts[f][k] += 1

    tot = {"exact": 0, "contains": 0, "wrong": 0, "missing": 0}
    for f in FIELDS:
        for k in tot:
            tot[k] += counts[f][k]

    print(f"Buecker2023 — CED/IED/MD, item = paper x field, micro.  papers scored: {n_papers}")
    print(f"cells: {sum(tot.values())}  (exact {tot['exact']}, contains {tot['contains']}, "
          f"wrong {tot['wrong']}, missing {tot['missing']})\n")
    for std in ("strict", "widened"):
        m = _from_counts(tot, std)
        print(f"{std.upper():8s} P={m['precision']:.3f}  R={m['recall']:.3f}  "
              f"F1={m['f1']:.3f}  Acc={m['accuracy']:.3f}   (CED={m['ced']} IED={m['ied']} MD={m['md']})")

    print("\nper-field  Strict F1 / Widened F1   (exact, contains, wrong, missing)")
    for f in FIELDS:
        c = counts[f]
        s, w = _from_counts(c, "strict"), _from_counts(c, "widened")
        print(f"  {f:18s} {s['f1']:.3f} / {w['f1']:.3f}    "
              f"({c['exact']}, {c['contains']}, {c['wrong']}, {c['missing']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
