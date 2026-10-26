"""Score Bennett 2023 (69 studies, v5 runs) under the SAME CED/IED/MD standard
as the Vu/Ng record, so all four meta-analyses sit on one scorer.

Gold = Jansen's d_long (the set Jansen scored). Runs = the v5 69-study set:
  data/runs/jansen_bennett2023_v5 (16) + _new10 (10) + _rest43 (43)

Item = one (study x field). Fields: Country, Population, Type, Area — all set-valued
(Country is effectively single-valued but may list several countries).

Usage:  PYTHONPATH=.:src python scripts/score_bennett_ced.py
"""
from __future__ import annotations

import importlib.util
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from eval._dashboard.build_dashboard import _from_counts
from eval._dashboard.common import classify_set

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
RUN_DIRS = ("jansen_bennett2023_v5", "jansen_bennett2023_new10", "jansen_bennett2023_rest43")
FIELDS = ("Country", "Population", "Type", "Area")

_spec = importlib.util.spec_from_file_location(
    "vb", str(REPO / "scripts" / "validate_bennett_vs_jansen.py"))
vb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vb)


def _key(s: str) -> str:
    """ASCII-fold study keys. d_long's 'Ziołkowska2017' is exported corrupted as
    'Zi�?kowska2017', so a fuzzy fallback is needed (see _match)."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(s)).lower())


def _match(run_name: str, gold_by_key: dict[str, str]) -> str | None:
    k = _key(run_name)
    if k in gold_by_key:
        return gold_by_key[k]
    best, score = None, 0.0
    for gk, gs in gold_by_key.items():
        r = SequenceMatcher(None, k, gk).ratio()
        if r > score:
            best, score = gs, r
    return best if score >= 0.85 else None


def main() -> int:
    dl = vb.load_d_long()
    # map folded key -> the exact gold study string (gold_set needs the original)
    gold_by_key = {_key(s): s for s in dl["study"].dropna().unique()}

    runs: dict[str, Path] = {}
    for d in RUN_DIRS:
        p = run_dir(d)
        if not p.exists():
            continue
        for s in p.iterdir():
            if (s / "paper_target.json").exists():
                runs[s.name] = s / "paper_target.json"

    counts = {f: {"exact": 0, "contains": 0, "wrong": 0, "missing": 0} for f in FIELDS}
    scored = 0
    for run_name, pt in sorted(runs.items()):
        study = _match(run_name, gold_by_key)
        if study is None:
            continue
        scored += 1
        e = json.loads(pt.read_text())
        for f in FIELDS:
            ref = vb.gold_set(dl, study, f, f)
            if not ref:
                continue
            got = (vb.norm_set(vb.extract_value(e, f) or "", f) if f == "Country"
                   else vb.norm_set(vb.extract_set(e, f), f))
            counts[f][classify_set(ref, got)] += 1

    print(f"Bennett 2023 — CED/IED/MD (same standard as Vu/Ng record) — {scored} studies\n")
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
