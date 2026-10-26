"""Score Jansen (2025)'s Bowes2023 LLM codings on **Jansen's own field set and units**.

This is deliberately NOT the same basis as our Bowes row in §2 of the cross-MA record:

  ours   : 9 fields (adds outcome_es, es_es, N_es — the per-effect-size numerics)
  Jansen : the 6 fields he actually coded (YearOfPub, CTType, COVID, Females, SampleType, Outcome)

and his `Females` is a **head-count** while the gold stores `Females_pct` + `N`, so the gold is
converted to a count (`round(pct * N / 100)`) to score him fairly on his own terms.

Item = one (paper x field), CED/IED/MD, micro — the same classifiers as everywhere else.
Field rules (chosen to match how Jansen coded, not how we extract):
  YearOfPub  scalar int, exact
  COVID      scalar Yes/No
  CTType     set   (gold vocab {General, Mix, Scenario, Specific, Stereotype})
  SampleType set   (gold vocab {Com, Mixed, Student}); his "Study 1: Com, Study 2: Com" is parsed to {Com}
  Outcome    set   of construct tokens (gold `outcomes` is pipe-separated)
  Females    coverage match on head-counts, tolerance +/-2% of the gold count

Usage:  PYTHONPATH=.:src python scripts/score_bowes_jansen_ced.py
"""
from __future__ import annotations

import io
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
sys.path.insert(0, str(REPO))

from eval._dashboard.build_dashboard import _from_counts  # noqa: E402
from eval._dashboard.common import classify_scalar, classify_set  # noqa: E402

JAR = JANSEN_DIR / "osfstorage-archive" / "coding_data.zip"
GS = REPO / "eval" / "bowes2023" / "gold_samplelevel.csv"
MODELS = ["gpt4", "gpt4_mini", "claude", "claude_mini",
          "llama", "llama_mini", "mistral", "mistral_mini"]
FIELDS = ("YearOfPub", "COVID", "CTType", "SampleType", "Outcome", "Females")
COL = {**{f: f for f in FIELDS}, "SampleType": "Sample"}
FEM_TOL_FRAC = 0.02

# tokens that appear in Jansen's SampleType cells but are structural, not categories
_STRUCT = re.compile(r"study\s*\d+\s*:?", re.I)


def _fold(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "",
                  unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower())


def _val(raw) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).split(";")[0].strip()
    return None if not s or s.upper() in ("NO_ANSWER", "NAN", "NONE") else s


def _toks(s: str) -> set[str]:
    s = _STRUCT.sub(" ", s)
    return {t.strip().lower() for t in re.split(r"[,\|/]", s) if t.strip()}


def _counts() -> dict:
    return {"exact": 0, "contains": 0, "wrong": 0, "missing": 0}


def _classify_females(gold: list[int], got: list[int]) -> str:
    if not got:
        return "missing"
    remaining = list(got)
    matched = 0
    for g in gold:
        for i, o in enumerate(remaining):
            if abs(o - g) <= max(1.0, FEM_TOL_FRAC * abs(g)):
                remaining.pop(i)
                matched += 1
                break
    if matched < len(gold):
        return "wrong"
    return "exact" if not remaining else "contains"


def main() -> int:
    g = pd.read_csv(GS)
    with zipfile.ZipFile(JAR) as z:
        df = pd.read_excel(io.BytesIO(z.read("coding_data/LLM_coding_clean_LL.xlsx")),
                           sheet_name="Bowes2023")
    before = len(df)
    df = df.drop_duplicates(subset="study", keep="first")
    dropped = before - len(df)

    gold_by = {_fold(p): sub for p, sub in g.groupby("paper_id")}
    rows = {}
    for _, r in df.iterrows():
        k = _fold(r["study"])
        if k in gold_by:
            rows[k] = r
    print("Bowes2023 — Jansen's LLMs on HIS OWN 6 fields/units (NOT our 9-field basis)")
    print(f"  gold papers: {len(gold_by)} | Jansen coded: {len(rows)} | dup rows dropped: {dropped}\n")

    hdr = f"{'model':14s} {'StrictF1':>9s} {'WidenedF1':>10s} {'W-Acc':>8s} {'MD':>5s}"
    print(hdr); print("-" * len(hdr))
    res, perfield_best = {}, {f: 0.0 for f in FIELDS}
    for m in MODELS:
        tot = _counts()
        pf = {f: _counts() for f in FIELDS}
        for k, r in rows.items():
            sub = gold_by[k]
            for f in FIELDS:
                col = f"{m}_{COL[f]}_clean"
                if col not in df.columns:
                    continue
                raw = _val(r[col])
                if f == "YearOfPub":
                    gv = int(sub["YearOfPub"].iloc[0])
                    ov = int(re.search(r"\d{4}", raw).group(0)) if raw and re.search(r"\d{4}", raw) else None
                    k_ = classify_scalar(ov == gv, ov is not None)
                elif f == "COVID":
                    gv = str(sub["COVID"].iloc[0]).strip().lower()
                    k_ = classify_scalar(bool(raw) and raw.strip().lower() == gv, bool(raw))
                elif f == "Females":
                    gold_ct = [int(round(p * n / 100.0))
                               for p, n in zip(sub["Females_pct"], sub["N"]) if pd.notna(p) and pd.notna(n)]
                    if not gold_ct:
                        continue
                    got = [int(round(float(x))) for x in re.findall(r"-?\d+(?:\.\d+)?", raw or "")]
                    k_ = _classify_females(gold_ct, got)
                else:
                    if f == "CTType":
                        ref = {str(x).strip().lower() for x in sub["CTType"].dropna()}
                    elif f == "SampleType":
                        ref = {str(x).strip().lower() for x in sub["SampleType"].dropna()}
                    else:
                        ref = set()
                        for o in sub["outcomes"].dropna():
                            ref |= {t.strip().lower() for t in str(o).split("|") if t.strip()}
                    if not ref:
                        continue
                    k_ = classify_set(ref, _toks(raw) if raw else set())
                tot[k_] += 1
                pf[f][k_] += 1
        if sum(tot.values()) == 0:
            continue
        s, w = _from_counts(tot, "strict"), _from_counts(tot, "widened")
        res[m] = (s["f1"], w["f1"])
        for f in FIELDS:
            if sum(pf[f].values()):
                perfield_best[f] = max(perfield_best[f], _from_counts(pf[f], "widened")["f1"])
        print(f"{m:14s} {s['f1']:9.3f} {w['f1']:10.3f} {w['accuracy']:8.3f} {w['md']:5d}")

    if res:
        bs, bw = max(r[0] for r in res.values()), max(r[1] for r in res.values())
        ms = sum(r[0] for r in res.values()) / len(res)
        mw = sum(r[1] for r in res.values()) / len(res)
        best = max(res, key=lambda k: res[k][1])
        print("-" * len(hdr))
        print(f"{'Jansen best':14s} {bs:9.3f} {bw:10.3f}   ({best})")
        print(f"{'Jansen mean':14s} {ms:9.3f} {mw:10.3f}")
        print("\nper-field best-of-8 (Widened F1):")
        for f in FIELDS:
            print(f"  {f:12s} {perfield_best[f]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
