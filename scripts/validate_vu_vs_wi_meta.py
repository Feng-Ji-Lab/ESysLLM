"""Validate Vu 2024 extraction outputs against Vu's own WI_meta.csv (paper truth).

This is the WI_meta-as-truth validator. It replaces the d_long-gold validator
because Jansen 2025's d_long.xlsx has documented coding errors for several Vu
papers (Exley2015 ↔ Exley2021 fully swapped; Grossman2014 ↔ Grossman2017
N_Self_Tmt swapped). See:
  docs/reports/2026-05-30-jansen-gold-vs-wi-meta.md

Truth source: Jansen2025/Vu2023_15/All_data/WI_meta.csv — Vu's hand-coding,
one row per (Tmt × Ctr) cell.

Validation rules:
  Design   — exact string match (lowercase)
  country  — exact string match (lowercase, normalized)
  info_cost — numeric tolerance ±0.011
  N_*_CI_* — MULTISET match per cell (one row per cell; replicated Ctr values
             across cells DO count, matching our per-cell output shape)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
WI = JANSEN_DIR / "Vu2023_15" / "All_data" / "WI_meta.csv"
RUNS = run_dir("jansen_vu2024")

AUTHOR_MAP = {
    "Bartling2014": ("Bartling", 2014),
    "Cerrone2019": ("Cerrone", 2019),
    "Conrads2013": ("Conrads", 2013),
    "Dana2007": ("Dana", 2007),
    "Exley2015": ("Exley", 2015),
    "Exley2021": ("Exley & Kessler", 2020),
    "Grossman2014": ("Grossman", 2014),
    "Grossman2017": ("Grossman & Van der Weele", 2017),
    "Jarke-Neuert2022": ("Jarke-Neuert", 2020),
    "Kappes2018": ("Kappes", 2018),
    "Larson2009": ("Larson", 2009),
    "Lind2019": ("Lind", 2019),
    "Matthey2011": ("Matthey", 2011),
    "Moradi2018": ("Moradi", 2018),
    "Stuber2019": ("Stuber", 2019),
}

N_VARS = ("N_Self_CI_Tmt", "N_Self_CI_Ctr", "N_Altr_CI_Ctr")


def load_wi() -> pd.DataFrame:
    df = pd.read_csv(WI)
    df.columns = [c.strip() for c in df.columns]
    return df


def wi_rows(wi: pd.DataFrame, paper: str) -> pd.DataFrame:
    a, y = AUTHOR_MAP[paper]
    return wi[wi["Authors"].str.contains(a, na=False, regex=False) & (wi["year"] == y)]


def wi_n_multiset(wi: pd.DataFrame, paper: str, var: str) -> Counter:
    """Multiset (preserves multiplicity) of cell counts from WI_meta rows."""
    return Counter(int(x) for x in wi_rows(wi, paper)[var].dropna())


def wi_scalar(wi: pd.DataFrame, paper: str, col: str) -> str | None:
    r = wi_rows(wi, paper)
    vals = r[col].dropna().unique().tolist()
    return str(vals[0]) if vals else None


def load_extraction(paper: str) -> dict | None:
    p = RUNS / paper / "paper_target.json"
    if not p.exists() or p.stat().st_size < 100:
        return None
    return json.loads(p.read_text())


def collect_n(extraction: dict, field: str) -> Counter:
    """Multiset of integer cell values from per-cell dict shape."""
    obj = extraction.get(field, {})
    if not isinstance(obj, dict):
        return Counter()
    out: list[int] = []
    for v in obj.values():
        if isinstance(v, list):
            out.extend(x for x in v if isinstance(x, int))
    return Counter(out)


def main() -> int:
    if not WI.exists():
        sys.exit(f"!! WI_meta not found: {WI}")
    wi = load_wi()

    papers = sorted(
        d.name for d in RUNS.iterdir()
        if d.is_dir() and (d / "paper_target.json").exists()
    )
    print(f"Validating {len(papers)} extracted Vu papers vs WI_meta (Vu's hand-coding)\n")

    correct = {v: 0.0 for v in ("Design", "country", "info_cost", *N_VARS)}
    total = {v: 0 for v in correct}
    per_paper = {p: {"score": 0.0, "max": 0} for p in papers}

    print(f"{'Paper':18s} {'Design':9s} {'country':18s} {'info_cost':12s} "
          f"{'N_Self_Tmt':18s} {'N_Self_Ctr':18s} {'N_Altr_Ctr':18s}")
    print("-" * 120)

    for p in papers:
        e = load_extraction(p)
        if e is None:
            print(f"{p:18s} no extraction")
            continue

        parts = [f"{p:18s}"]

        # Design
        ours = (e.get("Design") or "").strip().lower()
        truth_raw = wi_scalar(wi, p, "Design") or ""
        truth = truth_raw.strip().lower()
        ok = ours == truth and ours != ""
        correct["Design"] += ok; total["Design"] += 1
        per_paper[p]["score"] += int(ok); per_paper[p]["max"] += 1
        parts.append(f"{'✓' if ok else '✗'} {ours[:7]:7s}")

        # country (normalize US variants)
        def norm_country(s: str) -> str:
            s = s.strip().lower()
            return {"us": "united states", "usa": "united states"}.get(s, s)
        ours_c = norm_country(e.get("country") or "")
        truth_c = norm_country(wi_scalar(wi, p, "country") or "")
        ok = ours_c == truth_c and ours_c != ""
        correct["country"] += ok; total["country"] += 1
        per_paper[p]["score"] += int(ok); per_paper[p]["max"] += 1
        parts.append(f"{'✓' if ok else '✗'} {ours_c[:16]:16s}")

        # info_cost
        try: ours_v = float(e.get("info_cost", 0.0))
        except (TypeError, ValueError): ours_v = None
        try: truth_v = float(wi_scalar(wi, p, "info_cost"))
        except (TypeError, ValueError): truth_v = None
        ok = ours_v is not None and truth_v is not None and abs(ours_v - truth_v) <= 0.011
        correct["info_cost"] += ok; total["info_cost"] += 1
        per_paper[p]["score"] += int(ok); per_paper[p]["max"] += 1
        parts.append(f"{'✓' if ok else '✗'} {ours_v} vs {truth_v}".ljust(12)[:12])

        # N fields — multiset match (NO dedup; multiplicity is informative)
        for var in N_VARS:
            ours_c = collect_n(e, var)
            truth_c = wi_n_multiset(wi, p, var)
            overlap = sum((ours_c & truth_c).values())
            if ours_c == truth_c:
                score = 1.0
            elif sum(truth_c.values()) > 0:
                denom = max(sum(ours_c.values()), sum(truth_c.values()))
                score = overlap / denom if denom else 0
            else:
                # truth empty
                score = 1.0 if sum(ours_c.values()) == 0 else 0.0
            correct[var] += score
            total[var] += 1
            per_paper[p]["score"] += score; per_paper[p]["max"] += 1
            marker = "✓" if score == 1 else ("~" if score > 0 else "✗")
            ours_str = str(sorted(ours_c.elements()))[:7]
            truth_str = str(sorted(truth_c.elements()))[:7]
            parts.append(f"{marker} {ours_str} vs {truth_str}".ljust(18)[:18])

        print(" ".join(parts))

    print()
    print("=" * 88)
    print("AGGREGATE PER-VARIABLE ACCURACY (vs WI_meta, Vu's hand-coding)")
    print("=" * 88)
    print(f"{'Variable':18s} {'our %':>8s} {'jansen baseline':>16s} {'delta':>7s}")
    # Jansen baseline numbers stay the same (they are from Jansen's eval against
    # their flawed gold) — kept for orientation.
    jansen_pct = {
        "Design": 82.2, "country": 85.7, "info_cost": 24.0,
        "N_Self_CI_Tmt": 10.7, "N_Self_CI_Ctr": 22.1, "N_Altr_CI_Ctr": 12.9,
    }
    for var in ("Design", "country", "info_cost", *N_VARS):
        ours_pct = (correct[var] / total[var] * 100) if total[var] else 0
        jb = jansen_pct[var]
        print(f"{var:18s} {ours_pct:>7.1f}% {jb:>15.1f}% {ours_pct - jb:>+7.1f}")

    overall = sum(correct.values()) / sum(total.values()) * 100 if sum(total.values()) else 0
    print(f"{'OVERALL':18s} {overall:>7.1f}% {33.6:>15.1f}% {overall - 33.6:>+7.1f}")
    print()
    print(f"Per-paper completeness: {sum(p['score'] for p in per_paper.values()):.1f} / "
          f"{sum(p['max'] for p in per_paper.values())}")
    print()
    print("NOTE: This evaluates against WI_meta (Vu's own hand-coding). For")
    print("      orientation against Jansen's reported baseline, see")
    print("      scripts/validate_vu_vs_jansen.py — but be aware that script")
    print("      uses d_long.xlsx which has paper-swap bugs documented in")
    print("      docs/reports/2026-05-30-jansen-gold-vs-wi-meta.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
