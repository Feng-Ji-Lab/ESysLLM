"""Score Jansen (2025)'s Bowes2023 LLM codings on ALL **9** fields — the six descriptors
*plus* the three per-effect-size numerics (`outcome_es`, `es_es`, `N_es`) — so his result is
directly comparable to ours in `scripts/score_bowes_ced.py`.

Why this exists
---------------
`scripts/score_bowes_jansen_ced.py` scores him on the 6 descriptors only. That was based on the
belief that he never attempted effect sizes. **He did.** Supplement_A has a dedicated section
`## Prompts: Effect Size Variables` (line 5567) with a Bowes2023 prompt that asks for a JSON array
of `{outcome, es, N}` against the 55-construct whitelist. His per-effect-size codings are not in
`coding_data.zip` (that sheet carries only the 6 descriptors x 8 models); they live in
`Archive/Revision 2 files/d_long_final_v4.xlsx`, one row per gold effect size, with
`llm_code` = 1 correct / 0 attempted-but-wrong / NaN not-attempted.

Sources, per field group
------------------------
  6 descriptors : re-uses `score_bowes_jansen_ced.py`'s rules, i.e. the gold is converted into
                  HIS units (Females as a head-count +/-2%) — this *repairs* a unit bug of his own
                  scoring and is deliberately generous to him.
  3 es fields   : his own correctness labels from d_long, aggregated to our item granularity:
                    every gold ES of that paper correct  -> exact    (CED)
                    something attempted, not all correct -> wrong    (IED)
                    nothing attempted at all             -> missing  (MD)

Two ways this is generous to Jansen — state them whenever citing the output:
  1. **On the 3 es fields his `contains` bucket is 0 by construction.** His framework fixes Precision
     at 1.0 (over-extraction is never recorded), so a paper where he matched all gold *and* emitted
     extras lands in `exact`, where our own scorer would call it `contains` (= IED under Strict).
     That inflates his Strict on exactly the fields the comparison turns on. **Only the Widened
     column is a fair head-to-head.** (The 6 descriptors are classified from his raw text by our own
     classifiers, so they do produce `contains` — his Strict != his Widened overall.)
  2. The Females unit repair above. Scoring all 9 fields purely from his own d_long labels instead
     drops his best model to 0.670 Widened (Females collapses to 0.136).

Item = one (paper x field), CED/IED/MD, micro — identical to `scripts/score_bowes_ced.py`.

Usage:  PYTHONPATH=.:src python scripts/score_bowes_jansen_ced9.py
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import score_bowes_jansen_ced as J  # noqa: E402
from eval._dashboard.build_dashboard import _from_counts  # noqa: E402
from eval._dashboard.common import classify_scalar, classify_set  # noqa: E402

DLONG = JANSEN_DIR / "osfstorage-archive" / "Archive" / "Revision 2 files" / "d_long_final_v4.xlsx"
ES_FIELDS = ("outcome_es", "es_es", "N_es")

# LLM_coding_clean_LL.xlsx model name -> d_long model name
MODEL_MAP = {
    "gpt4": "gpt4_large", "gpt4_mini": "gpt4_mini",
    "claude": "claude_large", "claude_mini": "claude_mini",
    "llama": "llama_large", "llama_mini": "llama_mini",
    "mistral": "mistral_large", "mistral_mini": "mistral_mini",
}


def _counts() -> dict:
    return {"exact": 0, "contains": 0, "wrong": 0, "missing": 0}


def _descriptor_counts() -> dict:
    """Per-model, per-field counts for the 6 descriptors (score_bowes_jansen_ced.py rules)."""
    g = pd.read_csv(J.GS)
    with zipfile.ZipFile(J.JAR) as z:
        df = pd.read_excel(io.BytesIO(z.read("coding_data/LLM_coding_clean_LL.xlsx")),
                           sheet_name="Bowes2023")
    df = df.drop_duplicates(subset="study", keep="first")
    gold_by = {J._fold(p): sub for p, sub in g.groupby("paper_id")}
    rows = {J._fold(r["study"]): r for _, r in df.iterrows() if J._fold(r["study"]) in gold_by}

    out = {}
    for m in J.MODELS:
        pf = {f: _counts() for f in J.FIELDS}
        for key, r in rows.items():
            sub = gold_by[key]
            for f in J.FIELDS:
                col = f"{m}_{J.COL[f]}_clean"
                if col not in df.columns:
                    continue
                raw = J._val(r[col])
                if f == "YearOfPub":
                    gv = int(sub["YearOfPub"].iloc[0])
                    ov = int(re.search(r"\d{4}", raw).group(0)) if raw and re.search(r"\d{4}", raw) else None
                    k = classify_scalar(ov == gv, ov is not None)
                elif f == "COVID":
                    gv = str(sub["COVID"].iloc[0]).strip().lower()
                    k = classify_scalar(bool(raw) and raw.strip().lower() == gv, bool(raw))
                elif f == "Females":
                    gold_ct = [int(round(p * n / 100.0))
                               for p, n in zip(sub["Females_pct"], sub["N"])
                               if pd.notna(p) and pd.notna(n)]
                    if not gold_ct:
                        continue
                    got = [int(round(float(x))) for x in re.findall(r"-?\d+(?:\.\d+)?", raw or "")]
                    k = J._classify_females(gold_ct, got)
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
                    k = classify_set(ref, J._toks(raw) if raw else set())
                pf[f][k] += 1
        out[m] = pf
    return out


def _es_counts() -> dict:
    """Per-model, per-field counts for the 3 effect-size fields, from Jansen's own d_long labels."""
    gold_papers = {J._fold(p) for p in pd.read_csv(J.GS)["paper_id"].unique()}
    d = pd.read_excel(DLONG)
    d = d[d["meta"] == "Bowes2023"].copy()
    d["pk"] = d["study"].map(J._fold)
    d = d[d["pk"].isin(gold_papers) & d["var"].isin(ES_FIELDS)]

    out = {}
    for model, mdf in d.groupby("model"):
        pf = {f: _counts() for f in ES_FIELDS}
        for (_pk, var), rows in mdf.groupby(["pk", "var"]):
            n = len(rows)
            ok = int((rows["llm_code"] == 1).sum())
            bad = int((rows["llm_code"] == 0).sum())
            pf[var]["exact" if ok == n else ("missing" if ok + bad == 0 else "wrong")] += 1
        out[model] = pf
    return out


def main() -> int:
    desc, es = _descriptor_counts(), _es_counts()
    print("Bowes2023 — Jansen's 8 LLMs on ALL 9 fields (item = paper x field, micro)")
    print("  6 descriptors: his units (Females as head-count) | 3 es fields: his own d_long labels")
    print("  His es cells can never be `contains` (his framework records no over-extraction), which")
    print("  inflates his Strict on the decisive fields — compare on WIDENED only.\n")

    hdr = (f"{'model':14s} {'CED':>5s} {'IED':>5s} {'MD':>5s} {'9f Strict':>9s} {'9f Widened':>10s}"
           f" | {'6f Strict':>9s} {'6f Widened':>10s}")
    print(hdr)
    print("-" * len(hdr))

    res9, res6 = {}, {}
    for m in J.MODELS:
        t6 = _counts()
        for f in J.FIELDS:
            for k in t6:
                t6[k] += desc[m][f][k]
        t9 = dict(t6)
        for f in ES_FIELDS:
            for k in t9:
                t9[k] += es[MODEL_MAP[m]][f][k]
        s9, w9 = _from_counts(t9, "strict"), _from_counts(t9, "widened")
        s6, w6 = _from_counts(t6, "strict"), _from_counts(t6, "widened")
        res9[m], res6[m] = (s9, w9), (s6, w6)
        print(f"{m:14s} {w9['ced']:5d} {w9['ied']:5d} {w9['md']:5d} {s9['f1']:9.3f} {w9['f1']:10.3f}"
              f" | {s6['f1']:9.3f} {w6['f1']:10.3f}")

    print("-" * len(hdr))
    b9 = max(res9, key=lambda k: res9[k][1]["f1"])
    b6 = max(res6, key=lambda k: res6[k][1]["f1"])
    print(f"{'Jansen best':14s} {'':17s} {res9[b9][0]['f1']:9.3f} {res9[b9][1]['f1']:10.3f}"
          f" | {res6[b6][0]['f1']:9.3f} {res6[b6][1]['f1']:10.3f}   (9f: {b9} | 6f: {b6})")
    print(f"{'Jansen mean':14s} {'':17s} "
          f"{sum(r[0]['f1'] for r in res9.values()) / len(res9):9.3f} "
          f"{sum(r[1]['f1'] for r in res9.values()) / len(res9):10.3f}"
          f" | {sum(r[0]['f1'] for r in res6.values()) / len(res6):9.3f} "
          f"{sum(r[1]['f1'] for r in res6.values()) / len(res6):10.3f}")

    print("\nper-field Widened F1 (best-of-8 envelope — no single model achieves all of these):")
    for f in J.FIELDS:
        print(f"  {f:12s} {max(_from_counts(desc[m][f], 'widened')['f1'] for m in J.MODELS):.3f}")
    for f in ES_FIELDS:
        print(f"  {f:12s} {max(_from_counts(es[MODEL_MAP[m]][f], 'widened')['f1'] for m in J.MODELS):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
