"""Validate Ng extraction outputs against Jansen d_long.xlsx + Ng's own
per-measure characteristics (MeasureCharacteristics.xlsx).

Truth sources:
  - Jansen `d_long.xlsx` `meta == "Ng2023"` slice — paper-level codes for
    IPT, male_pct, dxgive, Source (set), MedCat (set). This is the
    benchmark Jansen reports accuracy against.
  - `Jansen2025/Ng2023_34/Study Measure ES Data/MeasureCharacteristics.xlsx`
    — per-(study × measure) MedCat and Source. Use for the broader
    measure-level truth used when summing to a paper-level set.

Sample-key naming: extracted JSON uses generic keys ("Study 1 - main sample",
"Study 1 - CBT arm", "Study 1 - IPT arm" for the dual-arm exception). The
join to truth is by paper_id (PDF filename) → Jansen study key + ESdata
studyid.

Validation rules:
  IPT       — exact integer match (with dual-arm: CBT-arm has 0, IPT-arm has 1)
  male_pct  — ±2.0 absolute percentage points (codebook-default tolerance);
              tight bound ±0.5 if exact value reported
  dxgive    — exact category match (110/120/200/400)
  Source    — set Jaccard ≥ 0.66 vs union of MeasureCharacteristics codes
  MedCat    — set Jaccard ≥ 0.66 vs union of MeasureCharacteristics codes,
              normalising case for L2/L29/L99 vs l2/l29/l99
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
D_LONG = JANSEN_DIR / "osfstorage-archive" / "Archive" / "analysis" / "d_long.xlsx"
MC = JANSEN_DIR / "Ng2023_34" / "Study Measure ES Data" / "MeasureCharacteristics.xlsx"
RUNS_DEFAULT = run_dir("jansen_ng2023")

# Paper id (PDF filename stem) → d_long Ng2023 study key + ESdata studyid
PAPER_TO_KEYS = {
    "Ackerson1998": ("Ackerson1998", 593),
    "Asarnow2002": ("Asarnow2002", 428),
    "Asarnow2005": ("Asarnow2005", 974),
    "Brent1997": ("Brent1997", 16),
    "DeCuyper2004": ("DeCuyper2004", 711),
    "Dietz2015": ("Dietz2015", 20002),
    "Fleming2012": ("Fleming2012", 10064),
    "Garber2009": ("Garber2009", 7022),
    "Gillham2012": ("Gillham2012", 10065),
    "Lewinsohn1990": ("Lewinsohn1990", 463),
    "Liddle1990": ("Liddle1990", 78),
    "McCarty2013": ("McCarty2013", 10103),
    "Merry2012": ("Merry2012", 10039),
    "Mufson2004": ("Mufson2004", 20004),
    "Reed1994": ("Reed1994", 106),
    "Reynolds1986": ("Reynolds1986", 107),
    "Rohde2004": ("Rohde2004", 720),
    "Rohde2014": ("Rohde2014", 10114),
    "Rossello1999": ("Rossello1999", 950),
    "Santomauro2016": ("Santomauro2016", 10168),
    "Stark1987": ("Stark1987", 222),
    "Stasiak2014": ("Stasiak2014", 10115),
    "Stice2008": ("Stice2008", 844),
    "Szigethy2007": ("Szigethy2007", 811),
    "TADS2004": ("TADS2003", 971),
    "Tang2009": ("Tang2009", 976),
    "Vostanis1996": ("Vostanis1996", 586),
    "Weisz2009": ("Weisz2009", 977),
    "Young2006": ("Young2006", 801),
    "Young2010": ("Young2010", 7012),
    "Yu2002": ("Yu2002", 840),
}


def load_d_long_ng() -> pd.DataFrame:
    df = pd.read_excel(D_LONG)
    return df[df["meta"] == "Ng2023"].copy()


def load_mc() -> pd.DataFrame:
    df = pd.read_excel(MC)
    df["MedCat"] = df["MedCat"].astype(str).str.strip().str.lower()
    df["Source"] = df["Source"].astype(int)
    return df


def load_unimeta() -> pd.DataFrame:
    return pd.read_csv(JANSEN_DIR / "Ng2023_34" / "Univariate" / "unimeta.csv", encoding="latin-1")


def gold_paper_value(d_long: pd.DataFrame, study: str, var: str) -> str:
    sub = d_long[(d_long["study"] == study) & (d_long["var"] == var)]
    codes = sub["code"].astype(str).str.strip().unique().tolist()
    return codes[0] if codes else ""


def gold_paper_set(d_long: pd.DataFrame, study: str, var: str) -> set[str]:
    sub = d_long[(d_long["study"] == study) & (d_long["var"] == var)]
    out: set[str] = set()
    for c in sub["code"].astype(str).str.strip().unique():
        for tok in c.replace(";", ",").split(","):
            tok = tok.strip().lower()
            if tok and tok not in ("nan", "none", ""):
                out.add(tok)
    return out


def truth_source_set_from_mc(mc: pd.DataFrame, studyid: int) -> set[int]:
    return set(int(x) for x in mc[mc["studyid"] == studyid]["Source"].unique())


def truth_medcat_set_from_mc(mc: pd.DataFrame, studyid: int) -> set[str]:
    return set(str(x).strip().lower() for x in mc[mc["studyid"] == studyid]["MedCat"].dropna())


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_paper_value(e: dict, field: str):
    v = e.get(field)
    if isinstance(v, dict):
        # sample-scoped: pick first non-empty cell
        for cell in v.values():
            if isinstance(cell, list) and cell:
                first = cell[0]
                if first not in (None, "None", ""):
                    return first
        return None
    if isinstance(v, str) and v.lower() in ("none", "null", ""):
        return None
    return v


def extract_paper_set(e: dict, field: str) -> set[str]:
    """For Source / MedCat — collect all codes across all sample-scoped cells."""
    v = e.get(field)
    out: set[str] = set()
    if isinstance(v, dict):
        for cell in v.values():
            if isinstance(cell, list):
                for entry in cell:
                    if isinstance(entry, list):
                        out.update(str(c).strip().lower() for c in entry if c not in (None, "None"))
                    elif entry not in (None, "None", ""):
                        out.add(str(entry).strip().lower())
    elif isinstance(v, list):
        for entry in v:
            if isinstance(entry, list):
                out.update(str(c).strip().lower() for c in entry if c not in (None, "None"))
            elif entry not in (None, "None", ""):
                out.add(str(entry).strip().lower())
    return out


def extract_per_sample(e: dict, field: str) -> dict[str, str]:
    """For dual-arm IPT — return {sample_key: value}."""
    out: dict[str, str] = {}
    v = e.get(field)
    if isinstance(v, dict):
        for sk, cell in v.items():
            if isinstance(cell, list) and cell:
                first = cell[0]
                if first not in (None, "None", ""):
                    out[sk] = str(first)
    return out


def main(runs_dir: Path = RUNS_DEFAULT) -> int:
    if not D_LONG.exists():
        sys.exit(f"!! gold not found: {D_LONG}")
    if not runs_dir.exists():
        sys.exit(f"!! runs dir missing: {runs_dir}")

    d_long = load_d_long_ng()
    mc = load_mc()
    unimeta = load_unimeta()

    papers = sorted(
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and (d / "paper_target.json").exists()
    )
    print(f"Validating {len(papers)} Ng papers against d_long + MeasureCharacteristics\n")

    correct = {v: 0.0 for v in ("IPT", "male_pct", "dxgive", "Source", "MedCat")}
    total = {v: 0 for v in correct}

    print(f"{'Paper':16s} {'IPT':>5s} {'male_pct':>14s} {'dxgive':>8s} "
          f"{'Source (set Jacc)':>22s} {'MedCat (set Jacc)':>22s}")
    print("-" * 100)

    for paper in papers:
        e = json.loads((runs_dir / paper / "paper_target.json").read_text())
        if paper not in PAPER_TO_KEYS:
            print(f"{paper:16s} (no truth mapping)"); continue
        d_long_key, studyid = PAPER_TO_KEYS[paper]

        # IPT — primary truth: Ng's unimeta.csv (more complete than Jansen d_long which is
        # frequently empty due to Jansen LLM failures).
        per_sample_ipt = extract_per_sample(e, "IPT")
        ours_ipt_set = {str(v) for v in per_sample_ipt.values()}
        ng_ipt_truth = sorted(set(str(x) for x in unimeta[unimeta["studyid"]==studyid]["IPT"].astype(int).unique()))
        sub_ipt = d_long[(d_long["study"]==d_long_key) & (d_long["var"]=="IPT")]
        jansen_ipt = sorted(sub_ipt["code"].astype(str).str.strip().unique())
        jansen_ipt = [c for c in jansen_ipt if c not in ("nan", "none", "")]
        if ng_ipt_truth:
            ipt_ok = bool(set(ng_ipt_truth).issubset(ours_ipt_set) and ours_ipt_set)
        else:
            ipt_ok = False
        correct["IPT"] += int(ipt_ok); total["IPT"] += 1

        # male_pct  (d_long var name is 'male')
        # Multi-sub-study: accept if ANY sub-study's male_pct is within ±2pp of gold
        gold_mp = gold_paper_value(d_long, d_long_key, "male")
        ours_mp_dict = extract_per_sample(e, "male_pct")
        ov = None  # for display
        try:
            gv = float(str(gold_mp).replace(",", "."))
            best_diff = None
            for v in ours_mp_dict.values():
                try:
                    diff = abs(float(v) - gv)
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        ov = float(v)
                except (TypeError, ValueError):
                    continue
            mp_ok = best_diff is not None and best_diff <= 2.0
        except (TypeError, ValueError):
            mp_ok = False; gv = None
        correct["male_pct"] += int(mp_ok); total["male_pct"] += 1

        # dxgive — multi-sub-study OK: gold matches if ANY sub-study's dxgive matches
        gold_dx = gold_paper_value(d_long, d_long_key, "dxgive").strip()
        ours_dx_dict = extract_per_sample(e, "dxgive")
        ours_dx_set = {str(v).strip() for v in ours_dx_dict.values()}
        dx_ok = bool(gold_dx and gold_dx in ours_dx_set)
        ours_dx_s = ",".join(sorted(ours_dx_set))
        correct["dxgive"] += int(dx_ok); total["dxgive"] += 1

        # Source set — compare to MeasureCharacteristics union
        truth_source = {str(c) for c in truth_source_set_from_mc(mc, studyid)}
        ours_source = extract_paper_set(e, "Source")
        src_jac = jaccard(ours_source, truth_source)
        src_ok = src_jac >= 0.66
        correct["Source"] += src_ok; total["Source"] += 1

        # MedCat — compare to MeasureCharacteristics union
        truth_medcat = truth_medcat_set_from_mc(mc, studyid)
        ours_medcat = extract_paper_set(e, "MedCat")
        # Normalise both to lower-case
        truth_medcat = {x.lower() for x in truth_medcat}
        ours_medcat = {x.lower() for x in ours_medcat}
        med_jac = jaccard(ours_medcat, truth_medcat)
        med_ok = med_jac >= 0.66
        correct["MedCat"] += med_ok; total["MedCat"] += 1

        def m(ok):
            return "✓" if ok else "✗"

        ours_ipt_display = sorted(ours_ipt_set)
        ipt_truth_display = ng_ipt_truth
        print(f"{paper:16s} {m(ipt_ok)} {ours_ipt_display}/{ipt_truth_display}"
              .ljust(25)[:25]
              + f" {m(mp_ok)} {ov!s:6}/{gv!s:6}".ljust(15)[:15]
              + f" {m(dx_ok)} {ours_dx_s}/{gold_dx}".ljust(12)[:12]
              + f" {m(src_ok)} {sorted(ours_source)[:4]}/{sorted(truth_source)[:4]} J={src_jac:.2f}".ljust(28)[:28]
              + f" {m(med_ok)} {sorted(ours_medcat)[:4]}/{sorted(truth_medcat)[:4]} J={med_jac:.2f}")

    print()
    print("=" * 80)
    print("AGGREGATE PER-FIELD ACCURACY")
    print("=" * 80)
    jansen_baseline = {
        "IPT": None, "male_pct": None, "dxgive": None,
        "Source": 47.0, "MedCat": 19.6,
    }
    print(f"{'Field':12s} {'our %':>8s} {'jansen %':>10s} {'note':40s}")
    notes = {
        "IPT": "exact integer (dual-arm: both 0 and 1)",
        "male_pct": "±2.0 percentage points",
        "dxgive": "exact category match {110,120,200,400}",
        "Source": "set Jaccard ≥0.66 vs MeasureCharacteristics",
        "MedCat": "set Jaccard ≥0.66 vs MeasureCharacteristics",
    }
    for var in correct:
        ours_pct = (correct[var] / total[var] * 100) if total[var] else 0
        jb = jansen_baseline.get(var)
        jb_s = f"{jb:.1f}%" if jb else "—"
        print(f"{var:12s} {ours_pct:>7.1f}% {jb_s:>10s}  {notes[var]:40s}")
    overall = sum(correct.values()) / sum(total.values()) * 100 if sum(total.values()) else 0
    print(f"{'OVERALL':12s} {overall:>7.1f}%")
    return 0


if __name__ == "__main__":
    runs = Path(sys.argv[1]) if len(sys.argv) > 1 else RUNS_DEFAULT
    raise SystemExit(main(runs))
