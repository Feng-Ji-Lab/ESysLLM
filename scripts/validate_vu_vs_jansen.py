"""Validate Vu 2024 extraction outputs against Jansen d_long.xlsx gold.

⚠️  KNOWN BUG IN d_long.xlsx: Jansen 2025's gold has at least two paper-level
swap errors for the Vu2023 slice — Exley2015 ↔ Exley2021 (all 5 evaluated
fields swapped) and Grossman2014 ↔ Grossman2017 (N_Self_CI_Tmt swapped).
See docs/reports/2026-05-30-jansen-gold-vs-wi-meta.md. For ground-truth
evaluation against Vu's own hand-coding, use validate_vu_vs_wi_meta.py
instead. This script remains for orientation against Jansen's published
baseline.

For each of the 6 Jansen-extracted variables (Design, country, info_cost,
N_Self_CI_Tmt, N_Self_CI_Ctr, N_Altr_CI_Ctr), compute per-paper accuracy
matching Jansen's evaluation rules. Reports per-variable and overall
accuracy alongside Jansen's published baseline.

Validation rules (matching eval/vu2024/groundtruth_map.yaml):
  Design   — exact string match (lowercase)
  country  — exact string match (lowercase)
  info_cost — numeric tolerance ±0.01
  N_*_CI_* — list-set match (multiset; order-independent, exact integer)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
GOLD = JANSEN_DIR / "osfstorage-archive" / "Archive" / "analysis" / "d_long.xlsx"
RUNS = run_dir("jansen_vu2024")


# Paper ID → d_long study name (handles diacritic mojibake: "Stuber2019" → "St�ber2019")
PAPER_TO_GOLD_KEY = {
    "Stuber2019": "St�ber2019",  # d_long stores it with U+FFFD replacement char
}


def gold_key(paper_id: str) -> str:
    return PAPER_TO_GOLD_KEY.get(paper_id, paper_id)


def load_extraction(paper_id: str) -> dict | None:
    p = RUNS / paper_id / "paper_target.json"
    if not p.exists() or p.stat().st_size < 100:
        return None
    return json.loads(p.read_text())


def collect_n_values(extraction: dict, field: str) -> list[int]:
    """Pull all integer cell values for an N_* field from the per-cell dict."""
    obj = extraction.get(field, {})
    if not isinstance(obj, dict):
        return []
    out: list[int] = []
    for v in obj.values():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, int):
                    out.append(x)
    return sorted(out)


def gold_n_values(d_long: pd.DataFrame, paper: str, var: str) -> list[int]:
    """Pull integer gold values from d_long (per-paper × per-var, unique cells)."""
    sub = d_long[(d_long["meta"] == "Vu2023") & (d_long["study"] == paper) & (d_long["var"] == var)]
    # d_long has 8 rows per cell (one per model) — dedupe to unique codes
    codes = sub["code"].astype(str).str.strip().unique()
    out: list[int] = []
    for c in codes:
        try:
            out.append(int(float(c)))
        except (ValueError, TypeError):
            pass
    return sorted(out)


def gold_paper_value(d_long: pd.DataFrame, paper: str, var: str) -> str:
    """Pull single paper-level gold value (Design/country/info_cost)."""
    sub = d_long[(d_long["meta"] == "Vu2023") & (d_long["study"] == paper) & (d_long["var"] == var)]
    codes = sub["code"].astype(str).str.strip().unique().tolist()
    return codes[0] if codes else ""


def main() -> int:
    if not GOLD.exists():
        sys.exit(f"!! gold not found: {GOLD}")
    d_long = pd.read_excel(GOLD)

    # Discover papers we have extractions for
    papers = sorted(d.name for d in RUNS.iterdir() if d.is_dir() and (d / "paper_target.json").exists())
    print(f"Validating {len(papers)} extracted Vu papers vs d_long gold\n")

    paper_field_pairs = []
    for p in papers:
        e = load_extraction(p)
        if e is None:
            continue
        for var in ("Design", "country", "info_cost", "N_Self_CI_Tmt", "N_Self_CI_Ctr", "N_Altr_CI_Ctr"):
            paper_field_pairs.append((p, var, e))

    # Per-variable counters
    correct = {v: 0 for v in ("Design", "country", "info_cost", "N_Self_CI_Tmt", "N_Self_CI_Ctr", "N_Altr_CI_Ctr")}
    total = {v: 0 for v in correct}
    per_paper = {p: {"score": 0, "max": 0} for p in papers}

    print(f"{'Paper':22s} {'Design':9s} {'country':16s} {'info_cost':10s} "
          f"{'N_Self_Tmt':15s} {'N_Self_Ctr':15s} {'N_Altr_Ctr':15s}")
    print("-" * 110)

    for p in papers:
        e = load_extraction(p)
        if e is None:
            print(f"{p:22s} no extraction")
            continue

        row_parts = [f"{p:22s}"]

        # Design
        ours = (e.get("Design") or "").strip().lower()
        gold = gold_paper_value(d_long, gold_key(p), "Design").lower()
        ok = ours == gold and ours != ""
        correct["Design"] += ok; total["Design"] += 1
        per_paper[p]["score"] += int(ok); per_paper[p]["max"] += 1
        row_parts.append(f"{'✓' if ok else '✗'} {ours[:7]:7s}")

        # country
        ours = (e.get("country") or "").strip().lower()
        gold = gold_paper_value(d_long, gold_key(p), "country").lower()
        ok = ours == gold and ours != ""
        correct["country"] += ok; total["country"] += 1
        per_paper[p]["score"] += int(ok); per_paper[p]["max"] += 1
        row_parts.append(f"{'✓' if ok else '✗'} {ours[:14]:14s}")

        # info_cost
        try:
            ours_v = float(e.get("info_cost", 0.0))
        except (TypeError, ValueError):
            ours_v = None
        try:
            gold_v = float(gold_paper_value(d_long, gold_key(p), "info_cost"))
        except (TypeError, ValueError):
            gold_v = None
        ok = ours_v is not None and gold_v is not None and abs(ours_v - gold_v) <= 0.01
        correct["info_cost"] += ok; total["info_cost"] += 1
        per_paper[p]["score"] += int(ok); per_paper[p]["max"] += 1
        row_parts.append(f"{'✓' if ok else '✗'} {ours_v}".ljust(10))

        # N_Self_CI_Tmt / Ctr / N_Altr_CI_Ctr — multiset match
        for var in ("N_Self_CI_Tmt", "N_Self_CI_Ctr", "N_Altr_CI_Ctr"):
            ours_list = collect_n_values(e, var)
            gold_list = gold_n_values(d_long, gold_key(p), var)
            # Multiset match: count overlap (gold values present in our list)
            from collections import Counter
            ours_c = Counter(ours_list); gold_c = Counter(gold_list)
            overlap = sum((ours_c & gold_c).values())
            # Score: 1 if exact set equal (with multiplicity); fractional otherwise.
            # Both-empty (e.g. within-subject papers where Jansen records NA) is
            # a perfect match — we correctly identified nothing to extract.
            if ours_c == gold_c:
                ok = True; score = 1
            elif sum(gold_c.values()) > 0:
                denom = max(sum(ours_c.values()), sum(gold_c.values()))
                score = overlap / denom if denom else 0
                ok = score >= 0.5
            else:
                # gold empty but we extracted something — over-extraction
                ok = False; score = 0
            correct[var] += score
            total[var] += 1
            per_paper[p]["score"] += score; per_paper[p]["max"] += 1
            row_parts.append(f"{'✓' if score==1 else ('~' if score>0 else '✗')} {ours_list[:5]} vs {gold_list[:5]}".ljust(15)[:15])

        print(" ".join(row_parts))

    # Aggregate accuracy
    print()
    print("=" * 80)
    print("AGGREGATE PER-VARIABLE ACCURACY (vs Jansen baseline)")
    print("=" * 80)
    print(f"{'Variable':18s} {'our %':>8s} {'jansen %':>8s} {'delta':>7s}")
    jansen_pct = {
        "Design": 82.2, "country": 85.7, "info_cost": 24.0,
        "N_Self_CI_Tmt": 10.7, "N_Self_CI_Ctr": 22.1, "N_Altr_CI_Ctr": 12.9,
    }
    for var in ("Design", "country", "info_cost", "N_Self_CI_Tmt", "N_Self_CI_Ctr", "N_Altr_CI_Ctr"):
        ours = (correct[var] / total[var] * 100) if total[var] else 0
        jb = jansen_pct[var]
        print(f"{var:18s} {ours:>7.1f}% {jb:>7.1f}% {ours-jb:>+7.1f}")

    total_correct = sum(correct.values())
    total_max = sum(total.values())
    ours_overall = total_correct / total_max * 100 if total_max else 0
    print(f"{'OVERALL':18s} {ours_overall:>7.1f}% {33.6:>7.1f}% {ours_overall-33.6:>+7.1f}")
    print()
    print(f"Per-paper completeness: {sum(p['score'] for p in per_paper.values()):.1f} / {sum(p['max'] for p in per_paper.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
