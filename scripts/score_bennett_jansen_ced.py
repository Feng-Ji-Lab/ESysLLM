"""Re-score Jansen (2025)'s Bennett2023 LLM codings on the SAME CED/IED/MD scorer used for
our extraction (`scripts/score_bennett_ced.py`), over the SAME studies.

Mirrors `scripts/score_buecker_jansen_ced.py`. Our extraction is re-scored on the identical
study set so both sides of the comparison are strictly paired.

Source: `coding_data/LLM_coding_clean_LL.xlsx`, sheet `Bennett2023`.
  Cell format "<value>; <confidence>"; "NO" = the model found nothing.
  Fields are set-valued: "Risk, Recovery; 85" -> {Risk, Recovery}.
  (Its `*_clean_2` siblings are empty, as on Buecker — use `*_clean`.)

Usage:  PYTHONPATH=.:src python scripts/score_bennett_jansen_ced.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
sys.path.insert(0, str(REPO / "scripts"))

from eval._dashboard.build_dashboard import _from_counts  # noqa: E402
from eval._dashboard.common import classify_set  # noqa: E402
from score_bennett_ced import FIELDS, RUN_DIRS, _key, _match, vb  # noqa: E402

JAR = JANSEN_DIR / "osfstorage-archive" / "coding_data.zip"
MODELS = ["gpt4", "gpt4_mini", "claude", "claude_mini",
          "llama", "llama_mini", "mistral", "mistral_mini"]


def _val(raw) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).split(";")[0].strip()
    return None if not s or s.upper() in ("NO", "NAN", "NONE") else s


def _counts() -> dict:
    return {"exact": 0, "contains": 0, "wrong": 0, "missing": 0}


def main() -> int:
    dl = vb.load_d_long()
    gold_by_key = {_key(s): s for s in dl["study"].dropna().unique()}

    # our runs
    runs: dict[str, Path] = {}
    for d in RUN_DIRS:
        p = run_dir(d)
        if p.exists():
            for s in p.iterdir():
                if (s / "paper_target.json").exists():
                    runs[s.name] = s / "paper_target.json"

    with zipfile.ZipFile(JAR) as z:
        df = pd.read_excel(io.BytesIO(z.read("coding_data/LLM_coding_clean_LL.xlsx")),
                           sheet_name="Bennett2023")
    before = len(df)
    df = df.drop_duplicates(subset="study", keep="first")
    dropped = before - len(df)

    # head-to-head set: studies with gold, present in BOTH our runs and Jansen's sheet
    ours_studies = {rn: _match(rn, gold_by_key) for rn in runs}
    ours_studies = {rn: st for rn, st in ours_studies.items() if st}
    jansen_rows = {}
    for _, row in df.iterrows():
        st = gold_by_key.get(_key(row["study"]))
        if st:
            jansen_rows[st] = row
    common = set(ours_studies.values()) & set(jansen_rows)

    print("Bennett2023 — Jansen's LLMs re-scored on OUR CED/IED/MD scorer")
    print(f"  our studies: {len(set(ours_studies.values()))} | Jansen coded: {len(jansen_rows)} "
          f"| HEAD-TO-HEAD SET: {len(common)} | dup LLM rows dropped: {dropped}\n")

    # ours, restricted to `common`
    ours = {f: _counts() for f in FIELDS}
    for rn, st in ours_studies.items():
        if st not in common:
            continue
        e = json.loads(runs[rn].read_text())
        for f in FIELDS:
            ref = vb.gold_set(dl, st, f, f)
            if not ref:
                continue
            got = (vb.norm_set(vb.extract_value(e, f) or "", f) if f == "Country"
                   else vb.norm_set(vb.extract_set(e, f), f))
            ours[f][classify_set(ref, got)] += 1
    ours_tot = {k: sum(ours[f][k] for f in FIELDS) for k in _counts()}

    hdr = f"{'model':14s} {'StrictF1':>9s} {'WidenedF1':>10s} {'W-Acc':>8s} {'MD':>5s}"
    print(hdr); print("-" * len(hdr))
    res = {}
    for m in MODELS:
        tot = _counts()
        for st in common:
            row = jansen_rows[st]
            for f in FIELDS:
                ref = vb.gold_set(dl, st, f, f)
                if not ref:
                    continue
                col = f"{m}_{f}_clean"
                raw = _val(row[col]) if col in df.columns else None
                got = vb.norm_set(raw or "", f)
                tot[classify_set(ref, got)] += 1
        if sum(tot.values()) == 0:
            continue
        s, w = _from_counts(tot, "strict"), _from_counts(tot, "widened")
        res[m] = (s["f1"], w["f1"])
        print(f"{m:14s} {s['f1']:9.3f} {w['f1']:10.3f} {w['accuracy']:8.3f} {w['md']:5d}")

    os_, ow = _from_counts(ours_tot, "strict"), _from_counts(ours_tot, "widened")
    print("-" * len(hdr))
    if res:
        bs, bw = max(r[0] for r in res.values()), max(r[1] for r in res.values())
        ms = sum(r[0] for r in res.values()) / len(res)
        mw = sum(r[1] for r in res.values()) / len(res)
        print(f"{'Jansen best':14s} {bs:9.3f} {bw:10.3f}")
        print(f"{'Jansen mean':14s} {ms:9.3f} {mw:10.3f}")
        print(f"{'OURS (same set)':14s} {os_['f1']:6.3f} {ow['f1']:10.3f} "
              f"{ow['accuracy']:8.3f} {ow['md']:5d}")
        print(f"\ndelta vs best: Strict {os_['f1']-bs:+.3f}  Widened {ow['f1']-bw:+.3f}")
        print(f"delta vs mean: Strict {os_['f1']-ms:+.3f}  Widened {ow['f1']-mw:+.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
