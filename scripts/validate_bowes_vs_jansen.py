"""Validate Bowes 2023 extraction outputs against the Bowes gold data, and
compare to Jansen 2025's published per-variable accuracy.

Bowes is a CORRELATES meta-analysis. We replicate EXACTLY the Jansen variables:
  study-level : YearOfPub, CTType, COVID, Outcome
  sample-level: Females (PERCENT female), SampleType (Jansen var "Sample")
(The effect-size triple outcome/es/N is a separate phase-2 extractor.)

Truth source:
  eval/bowes2023/gold_samplelevel.csv (built from RDataFile2023Final.xlsx
  'For R'), one row per SAMPLE. Study-level fields take the paper value;
  sample-level fields are matched per sample (greedy by N).

Modes:
  --baseline   print Jansen's published per-variable accuracy ranges (the
               numbers we aim to beat) — needs no extraction run.
  (default)    score our paper_target.json runs in data/runs/jansen_bowes2023/.

KEY: gold `Females` is a PERCENT (0-100). Jansen extracted an absolute COUNT
and scored ~0.03 — our schema targets the percent, so a fair re-score here is
expected to be far higher; that is a schema-alignment fix, reported honestly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
GOLD = REPO / "eval" / "bowes2023" / "gold_samplelevel.csv"
GOLD_ES = REPO / "eval" / "bowes2023" / "gold_effectsizes.csv"
RUNS_DEFAULT = run_dir("jansen_bowes2023")
ES_TOL = 0.015  # |Δr| for an es match (r usually reported to 2 decimals)

STUDY_VARS = ("YearOfPub", "CTType", "COVID", "Outcome")
SAMPLE_VARS = ("Females", "SampleType")

# Jansen published per-variable accuracy, min-max across their 10 models
# (from osfstorage-archive/.../d_acc_combined.xlsx, meta=='Bowes2023').
JANSEN_BASELINE = {
    "YearOfPub":  (96.5, 100.0),
    "CTType":     (39.2, 44.8),   # only ensembles reported
    "Females":    (3.1, 7.7),     # COUNT-vs-PERCENT artifact
    "SampleType": (45.8, 81.0),   # Jansen var "Sample"
    "COVID":      (54.5, 94.7),
    "Outcome":    (19.0, 81.4),
}

JANSEN_ES_BASELINE = {
    "outcome_es": (26.6, 60.8),
    "es_es":      (15.6, 26.2),   # the headline 0.26 differentiator
    "N_es":       (45.1, 61.6),
}

FEMALES_TOL = 1.0       # pp for exact credit
FEMALES_FALLBACK = 3.0  # pp for partial credit


# ----------------------------------------------------------------- normalization
def norm_tok(s) -> str:
    return str(s).strip().lower().replace(".", "")


def to_set(raw) -> set[str]:
    """Flatten a gold '|'-string or our nested list into a lowercase token set."""
    out: set[str] = set()
    stack = [raw]
    while stack:
        x = stack.pop()
        if x is None:
            continue
        if isinstance(x, (list, tuple, set)):
            stack.extend(x)
        else:
            for part in str(x).replace("|", ",").replace(";", ",").split(","):
                t = norm_tok(part)
                if t and t not in ("nan", "none", ""):
                    out.add(t)
    return out


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ----------------------------------------------------------------- read our run
def cell_first(field: dict, sample_key: str | None = None):
    """First non-null scalar for a field; if sample_key given, that key only."""
    return field  # (legacy helper kept for signature compatibility; unused)


def match_samples(our: list[dict], gold: pd.DataFrame) -> dict[int, dict]:
    """Greedy gold-SampleID -> our sample dict by closest N (1:1 for single sample)."""
    mapping: dict[int, dict] = {}
    avail = list(our)
    for _, grow in gold.sort_values("N", ascending=False).iterrows():
        if not avail:
            break
        gn = grow["N"]
        avail.sort(key=lambda s: abs((s.get("N") or 0) - gn))
        mapping[int(grow["SampleID"])] = avail.pop(0)
    return mapping


# ----------------------------------------------------------------- baseline
def run_baseline() -> int:
    print("Jansen 2025 published Bowes accuracy (min-max across 10 models) — the bar:\n")
    print(f"{'Variable':12s} {'Jansen range':>16s}   note")
    notes = {
        "YearOfPub": "easy",
        "CTType": "hard (only ensembles reported)",
        "Females": "COUNT-vs-PERCENT artifact — we target percent",
        "SampleType": "Jansen var 'Sample' (recruitment)",
        "COVID": "easy-ish",
        "Outcome": "construct set; PyPDF2 table-reading weak",
    }
    for v in ("YearOfPub", "CTType", "Females", "SampleType", "COVID", "Outcome"):
        lo, hi = JANSEN_BASELINE[v]
        print(f"{v:12s} {f'{lo}-{hi}%':>16s}   {notes[v]}")
    return 0


# ----------------------------------------------------------------- scoring
def run_scoring(runs_dir: Path) -> int:
    gold = pd.read_csv(GOLD)
    gold_papers = set(gold["paper_id"].unique())
    papers = sorted(
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and (d / "extraction.json").exists()
    ) if runs_dir.exists() else []

    if not papers:
        print(f"No extraction.json runs in {runs_dir} yet.")
        print(f"(gold ready for {len(gold_papers)} pilot papers; run scripts/extract_bowes.py.)")
        print("\nRun with --baseline to print the Jansen bar.")
        return 0

    acc = {v: [] for v in STUDY_VARS + SAMPLE_VARS}      # per-unit correctness
    outcome_pr = []  # (precision, recall, jaccard) per paper
    rows_print = []

    for paper in papers:
        if paper not in gold_papers:
            rows_print.append(f"{paper:16s}  (no gold — unscored)")
            continue
        e = json.loads((runs_dir / paper / "extraction.json").read_text())
        study = e.get("study", {}) or {}
        our_smp = e.get("samples", []) or []
        es_rows = e.get("effect_sizes", []) or []
        gsub = gold[gold["paper_id"] == paper]
        grow = gsub.iloc[0]

        # ---- study-level (one unit per paper) ----
        try:
            yr_ok = int(float(study.get("YearOfPub"))) == int(grow["YearOfPub"])
        except (TypeError, ValueError):
            yr_ok = False
        acc["YearOfPub"].append(int(yr_ok))

        ct_g = to_set(list(gsub["CTType"].unique()))
        ct_o = to_set(study.get("CTType"))
        acc["CTType"].append(int(jaccard(ct_o, ct_g) >= 0.5))

        cov_g = norm_tok(grow["COVID"])
        cov_o = norm_tok(study.get("COVID"))
        acc["COVID"].append(int(cov_o == cov_g))

        # Outcome (study-level) = union of effect-size outcomes (derived)
        out_g = to_set("|".join(gsub["outcomes"].dropna().astype(str)))
        out_o = to_set([r.get("outcome") for r in es_rows])
        inter = len(out_o & out_g)
        prec = inter / len(out_o) if out_o else 0.0
        rec = inter / len(out_g) if out_g else 0.0
        jac = jaccard(out_o, out_g)
        outcome_pr.append((prec, rec, jac))
        acc["Outcome"].append(int(jac >= 0.5))

        # ---- sample-level (per matched sample) ----
        sid_to_smp = match_samples(our_smp, gsub)
        fem_marks, st_marks = [], []
        for _, gr in gsub.iterrows():
            smp = sid_to_smp.get(int(gr["SampleID"]), {})
            try:
                d = abs(float(smp.get("female_pct")) - float(gr["Females_pct"]))
                fem_ok, fem_part = d <= FEMALES_TOL, d <= FEMALES_FALLBACK
            except (TypeError, ValueError):
                fem_ok = fem_part = False
            acc["Females"].append(int(fem_ok))
            fem_marks.append("✓" if fem_ok else ("~" if fem_part else "✗"))
            st_ok = norm_tok(smp.get("recruitment")) == norm_tok(gr["SampleType"])
            acc["SampleType"].append(int(st_ok))
            st_marks.append("✓" if st_ok else "✗")

        rows_print.append(
            f"{paper:16s} yr={'✓' if yr_ok else '✗'} "
            f"CT={'✓' if jaccard(ct_o,ct_g)>=0.5 else '✗'} "
            f"COVID={'✓' if cov_o==cov_g else '✗'} "
            f"Out(P/R={prec:.2f}/{rec:.2f}) "
            f"Fem={''.join(fem_marks)} ST={''.join(st_marks)}"
        )

    print(f"Scoring {len([p for p in papers if p in gold_papers])} Bowes runs "
          f"vs gold ({GOLD.name})\n")
    for r in rows_print:
        print(" ", r)

    print("\n" + "=" * 72)
    print("PER-VARIABLE ACCURACY  vs  Jansen published range")
    print("=" * 72)
    print(f"{'Variable':12s} {'ours':>7s} {'n':>4s}   {'Jansen':>14s}")
    for v in ("YearOfPub", "CTType", "Females", "SampleType", "COVID", "Outcome"):
        vals = acc[v]
        ours = sum(vals) / len(vals) * 100 if vals else 0.0
        lo, hi = JANSEN_BASELINE[v]
        flag = "  <-- beats" if vals and ours > hi else ""
        print(f"{v:12s} {ours:>6.1f}% {len(vals):>4d}   {f'{lo}-{hi}%':>14s}{flag}")

    if outcome_pr:
        mp = sum(p for p, _, _ in outcome_pr) / len(outcome_pr) * 100
        mr = sum(r for _, r, _ in outcome_pr) / len(outcome_pr) * 100
        mj = sum(j for _, _, j in outcome_pr) / len(outcome_pr) * 100
        print(f"\nOutcome detail: mean precision={mp:.1f}%  recall={mr:.1f}%  Jaccard={mj:.1f}%")
    print("\nNote: Females scored as % (±1pp exact, ±3pp partial). Jansen's 3-8% is a "
          "count-vs-percent\nartifact; our higher number is a schema-alignment fix, not a "
          "multimodal-method win.")

    score_effect_sizes(runs_dir)
    return 0


def score_effect_sizes(runs_dir: Path) -> None:
    """Score phase-2 effect_sizes.json vs gold_effectsizes.csv (outcome_es / es_es / N_es)."""
    if not GOLD_ES.exists():
        return
    gold = pd.read_csv(GOLD_ES)
    runs = sorted(
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and (d / "extraction.json").exists()
    ) if runs_dir.exists() else []
    if not runs:
        return

    g_out_hit = g_es_hit = g_n_hit = g_total = 0          # recall side (per gold ES)
    p_match = p_total = 0                                   # precision side (per extracted ES)
    rows = []
    for paper in runs:
        if paper not in set(gold["paper_id"]):
            continue
        grows = [
            (norm_tok(r.outcome), float(r.es), r.N)
            for r in gold[gold["paper_id"] == paper].itertuples()
        ]
        data = json.loads((runs_dir / paper / "extraction.json").read_text())
        ex = []
        for r in data.get("effect_sizes", []):
            try:
                ex.append([norm_tok(r.get("outcome")), float(r.get("es")), r.get("N"), False])
            except (TypeError, ValueError):
                continue
        po = pe = pn = 0
        for go, ge, gn in grows:
            g_total += 1
            # best unused extracted row with same outcome
            cands = [r for r in ex if not r[3] and r[0] == go]
            if not cands:
                continue
            po += 1; g_out_hit += 1
            best = min(cands, key=lambda r: abs(r[1] - ge))
            if abs(best[1] - ge) <= ES_TOL:
                best[3] = True
                pe += 1; g_es_hit += 1
                try:
                    # N correct if exact or within 2% of gold (analytic-n slack)
                    if gn is not None and abs(float(best[2]) - float(gn)) <= max(2, 0.02 * float(gn)):
                        pn += 1; g_n_hit += 1
                except (TypeError, ValueError):
                    pass
        p_total += len(ex)
        p_match += sum(1 for r in ex if r[3])
        rows.append(f"{paper:16s} gold={len(grows):2d} ext={len(ex):2d} "
                    f"outcome✓={po} es✓={pe} N✓={pn}")

    print("\n" + "=" * 72)
    print("PHASE-2 EFFECT SIZES  (outcome / es / N)  vs Jansen published range")
    print("=" * 72)
    for r in rows:
        print(" ", r)
    if g_total:
        o = g_out_hit / g_total * 100
        e = g_es_hit / g_total * 100
        n = g_n_hit / g_total * 100
        prec = p_match / p_total * 100 if p_total else 0.0
        print(f"\n{'Variable':12s} {'ours(recall)':>13s} {'Jansen':>14s}")
        for var, val in (("outcome_es", o), ("es_es", e), ("N_es", n)):
            lo, hi = JANSEN_ES_BASELINE[var]
            flag = "  <-- beats" if val > hi else ""
            print(f"{var:12s} {val:>12.1f}% {f'{lo}-{hi}%':>14s}{flag}")
        print(f"\nes recall={e:.1f}%  es precision={prec:.1f}%  "
              f"(gold n={g_total}, extracted n={p_total}; es match |Δr|≤{ES_TOL})")
        print("Recall = gold correlations recovered with matching outcome+es. "
              "Jansen scored\nper-effect-size; our recall is the comparable number to their es_es ~0.16-0.26.")


def main() -> int:
    if "--baseline" in sys.argv[1:]:
        run_baseline()
        print("\nPhase-2 effect-size bar (Jansen):")
        for v, (lo, hi) in JANSEN_ES_BASELINE.items():
            print(f"  {v:12s} {lo}-{hi}%")
        return 0
    if not GOLD.exists():
        sys.exit(f"!! gold not found: {GOLD} (run the gold builder first)")
    runs = Path(next((a for a in sys.argv[1:] if not a.startswith("-")), RUNS_DEFAULT))
    return run_scoring(runs)


if __name__ == "__main__":
    raise SystemExit(main())
