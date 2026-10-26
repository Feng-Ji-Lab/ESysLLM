"""Re-score Jansen (2025)'s own Buecker2023 LLM codings on the IDENTICAL CED/IED/MD scorer
used for our extraction (`scripts/score_buecker_ced.py`), over the IDENTICAL 99 studies.

This is what docs/reports/2026-07-01-cross-ma-coverage-match-record.md §3 requires: a
head-to-head against Jansen's models re-scored with the same method, not their published
per-variable accuracies (a different scorer and granularity).

Source: Jansen's `coding_data/LLM_coding_clean_LL.xlsx`, sheet `Buecker2023`
  (188 studies x 8 models x 6 fields).
  Cell format: "<value>; <confidence>", value "NO" = the model found nothing.
  Enum fields carry the gold's own codes ("1 = Life Satisfaction, 2 = Positive Affect").

NOTE: each field also has a sibling `*_clean_2` column, but it is **entirely empty**
(0 / 9024 cells populated) — a vestigial column, NOT a second replicate coding. Only
`*_clean` carries data (97.5% filled). Scoring `_clean_2` as a replicate would mark every
cell "missing" and halve the reported F1.

Usage:  PYTHONPATH=.:src python scripts/score_buecker_jansen_ced.py
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from eval._dashboard.build_dashboard import _from_counts  # noqa: E402
from score_buecker_ced import FIELDS, classify_cell  # noqa: E402
from validate_buecker_vs_jansen import (  # noqa: E402
    ETH, GOLD_ALIAS, JAR, OUT, SAMP, STUDIES, load_gold_descriptors,
)

MODELS = ["gpt4", "gpt4_mini", "claude", "claude_mini",
          "llama", "llama_mini", "mistral", "mistral_mini"]
# their column stem per our field name
COL = {"yearT1": "YearT1", "country": "Country", "Outcome_variable": "Outcome_variable",
       "sample_type": "sample_type", "ethnicity": "ethnicity", "lag": "Lag"}


def _val(raw) -> str | None:
    """'2014; 60' -> '2014';  'NO; 95' -> None;  NaN -> None."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).split(";")[0].strip()
    if not s or s.upper() in ("NO", "NAN", "NONE"):
        return None
    return s


def _codes(s: str) -> list[str]:
    """'1 = Life Satisfaction, 2 = Positive Affect' -> ['1','2'];  '2, 3' -> ['2','3']."""
    return [m.group(1) for tok in s.split(",") if (m := re.match(r"\s*(\d)", tok))]


def decode(field: str, raw) -> object:
    s = _val(raw)
    if s is None:
        return None
    if field == "yearT1":
        m = re.search(r"(\d{4})", s)
        return float(m.group(1)) if m else None
    if field == "lag":
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(m.group(0)) if m else None
    if field == "country":
        return s
    if field == "Outcome_variable":
        return [OUT[c] for c in _codes(s) if c in OUT]  # ignore their "6 = Others"
    if field == "sample_type":
        cs = _codes(s)
        return SAMP.get(cs[0]) if cs else None  # multi-code answers: take the first
    if field == "ethnicity":
        cs = _codes(s)
        return ETH.get(cs[0]) if cs else None
    return None


def _by_label() -> dict:
    """Jansen's LLM sheet and his gold sheet use DIFFERENT label spaces for some studies
    (LLM "Berghuis2020" vs gold "Borghuis2019"). Accept both, else those rows are silently dropped."""
    out = {}
    for s in STUDIES:
        out[s] = s
        out[GOLD_ALIAS.get(s, s)] = s
    return out


def score(df: pd.DataFrame, gold: dict, model: str, rep: str, common: set) -> dict:
    tot = {"exact": 0, "contains": 0, "wrong": 0, "missing": 0}
    by_label = _by_label()
    for _, row in df.iterrows():
        st = by_label.get(str(row["study"]))
        if st is None or st not in common:
            continue
        for f in FIELDS:
            col = f"{model}_{COL[f]}{rep}"
            if col not in df.columns:
                continue
            k = classify_cell(f, gold[st].get(f), decode(f, row[col]))
            if k is not None:
                tot[k] += 1
    return tot


def score_ours(gold: dict, common: set) -> dict:
    """Our extraction over the SAME study set, through the SAME classifiers."""
    from score_buecker_ced import _extracted
    tot = {"exact": 0, "contains": 0, "wrong": 0, "missing": 0}
    for st in sorted(common):
        ext = _extracted(st)
        if ext is None:
            continue
        for f in FIELDS:
            k = classify_cell(f, gold[st].get(f), ext.get(f))
            if k is not None:
                tot[k] += 1
    return tot


def main() -> int:
    gold = load_gold_descriptors()
    with zipfile.ZipFile(JAR) as z:
        df = pd.read_excel(io.BytesIO(z.read("coding_data/LLM_coding_clean_LL.xlsx")),
                           sheet_name="Buecker2023")

    # Jansen's sheet contains DUPLICATE rows (Chen2020, Zhang2017) — dedupe, else double-counted.
    # Only Chen2020 is in our corpus.
    before = len(df)
    df = df.drop_duplicates(subset="study", keep="first")
    dropped = before - len(df)

    # Head-to-head must use the INTERSECTION: Garcia-Pena2013 has gold but Jansen never coded it.
    by_label = _by_label()
    coded = {by_label[l] for l in df["study"].astype(str) if l in by_label}
    common = coded & set(gold)
    only_ours = sorted(set(gold) - common)

    print("Jansen's Buecker2023 models re-scored on OUR CED/IED/MD scorer")
    print(f"  gold studies: {len(gold)} | Jansen coded: {len(coded & set(gold))} | "
          f"HEAD-TO-HEAD SET: {len(common)}")
    print(f"  duplicate LLM rows dropped: {dropped} (Chen2020, Zhang2017)")
    print(f"  in our gold but never coded by Jansen: {only_ours}\n")

    hdr = (f"{'model':14s} {'StrictF1':>9s} | {'W-P':>6s} {'W-R':>6s} {'W-F1':>7s} "
           f"{'W-Acc':>7s} {'CED':>5s} {'IED':>5s} {'MD':>4s}")
    print(hdr)
    print("-" * len(hdr))
    rows = {}
    for m in MODELS:
        tot = score(df, gold, m, "_clean", common)
        if sum(tot.values()) == 0:
            print(f"{m:14s}  (no columns)")
            continue
        s, w = _from_counts(tot, "strict"), _from_counts(tot, "widened")
        rows[m] = (s["f1"], w["f1"])
        print(f"{m:14s} {s['f1']:9.3f} | {w['precision']:6.3f} {w['recall']:6.3f} {w['f1']:7.3f} "
              f"{w['accuracy']:7.3f} {w['ced']:5d} {w['ied']:5d} {w['md']:4d}")

    ot = score_ours(gold, common)
    os_, ow = _from_counts(ot, "strict"), _from_counts(ot, "widened")
    if rows:
        bs = max(r[0] for r in rows.values())
        bw = max(r[1] for r in rows.values())
        ms = sum(r[0] for r in rows.values()) / len(rows)
        mw = sum(r[1] for r in rows.values()) / len(rows)
        print("-" * len(hdr))
        print(f"{'Jansen best':14s} {bs:9.3f} | {'':6s} {'':6s} {bw:7.3f}")
        print(f"{'Jansen mean':14s} {ms:9.3f} | {'':6s} {'':6s} {mw:7.3f}")
        print(f"{'OURS (same set)':14s} {os_['f1']:9.3f} | {ow['precision']:6.3f} {ow['recall']:6.3f} "
              f"{ow['f1']:7.3f} {ow['accuracy']:7.3f} {ow['ced']:5d} {ow['ied']:5d} {ow['md']:4d}")
        print(f"\ndelta vs best:  Strict {os_['f1']-bs:+.3f}   Widened {ow['f1']-bw:+.3f}")
        print(f"delta vs mean:  Strict {os_['f1']-ms:+.3f}   Widened {ow['f1']-mw:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
