"""Score Jansen (2025)'s Ng2023 / Vu2023 LLM codings on the SAME CED/IED/MD scorer used for
our dashboard rows, by feeding his values through `goldlib_{ng,vu}.evaluate` — i.e. the exact
same gold and the exact same classifiers.

Only JANSEN is scored here (our numbers stay as published in §2 of the cross-MA record).

Source: `coding_data/LLM_coding_clean_LL.xlsx`, sheets `Ng2023`, `Vu2023`.
  Cell format "<value>; <confidence>"; "NO" = model found nothing.
  `*_clean_2` siblings are empty (as on Buecker) — use `*_clean`.

IMPORTANT CAVEAT (stated in the record): several gold fields are **multisets over samples**
(Vu `N_*`, Ng `IPT`/`Source`/`MedCat`), while Jansen coded a single value per study. His score
on those fields is therefore depressed by coding granularity, not only model quality.

Usage:  PYTHONPATH=.:src python scripts/score_ng_vu_jansen_ced.py
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

from eval._dashboard import goldlib_ng, goldlib_vu  # noqa: E402
from eval._dashboard.build_dashboard import _from_counts  # noqa: E402
from eval._dashboard.common import GoldNotAvailable  # noqa: E402

JAR = JANSEN_DIR / "osfstorage-archive" / "coding_data.zip"
MODELS = ["gpt4", "gpt4_mini", "claude", "claude_mini",
          "llama", "llama_mini", "mistral", "mistral_mini"]

# our field name -> Jansen's column stem
NG_COL = {"IPT": "IPT", "male_pct": "male", "dxgive": "dxgive",
          "Source": "Source", "MedCat": "MedCat"}
VU_COL = {f: f for f in goldlib_vu.EVALUATED_FIELDS}


def _fold(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "",
                  unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower())


def _val(raw) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).split(";")[0].strip()
    return None if not s or s.upper() in ("NO", "NAN", "NONE") else s


def _tokens(s: str) -> list[str]:
    return [t.strip() for t in s.split(",") if t.strip()]


def _fake_target_ng(field: str, raw) -> dict:
    """Wrap a Jansen cell into the paper_target shape goldlib_ng.evaluate expects."""
    s = _val(raw)
    if s is None:
        return {}
    if field == "male_pct":
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return {field: {"s0": [m.group(0)]}} if m else {}
    if field in ("IPT", "dxgive"):
        return {field: {f"s{i}": [t] for i, t in enumerate(_tokens(s))}}
    # Source / MedCat -> flat set
    return {field: {"s0": _tokens(s)}}


def _fake_target_vu(field: str, raw) -> dict:
    s = _val(raw)
    if s is None:
        return {}
    if field == "Design":
        # gold says "Between-subject"; Jansen's models say "Between-subject design".
        # Strip the redundant suffix, else every cell scores `wrong` on a formatting artefact.
        return {field: re.sub(r"\s*design\s*$", "", s, flags=re.I)}
    if field == "country":
        return {field: s}
    if field == "info_cost":
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return {field: float(m.group(0))} if m else {}
    ints = [int(round(float(x))) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]
    return {field: {"s0": ints}} if ints else {}


def run(sheet: str, mod, colmap: dict, faker, paper_ids: set) -> None:
    with zipfile.ZipFile(JAR) as z:
        df = pd.read_excel(io.BytesIO(z.read("coding_data/LLM_coding_clean_LL.xlsx")),
                           sheet_name=sheet)
    df = df.drop_duplicates(subset="study", keep="first")
    by_fold = {_fold(p): p for p in paper_ids}
    rows = {}
    for _, r in df.iterrows():
        p = by_fold.get(_fold(r["study"]))
        if p:
            rows[p] = r
    fields = mod.EVALUATED_FIELDS

    print(f"\n=== {sheet} — Jansen's LLMs on our CED/IED/MD scorer "
          f"({len(rows)} studies scored, fields={len(fields)}) ===")
    hdr = f"{'model':14s} {'StrictF1':>9s} {'WidenedF1':>10s} {'W-Acc':>8s} {'MD':>5s}"
    print(hdr); print("-" * len(hdr))
    res = {}
    for m in MODELS:
        tot = {"exact": 0, "contains": 0, "wrong": 0, "missing": 0}
        for pid, r in rows.items():
            for f in fields:
                col = f"{m}_{colmap[f]}_clean"
                if col not in df.columns:
                    continue
                try:
                    ev = mod.evaluate(pid, f, faker(f, r[col]))
                except GoldNotAvailable:
                    continue
                tot[ev.klass] += 1
        if sum(tot.values()) == 0:
            continue
        s, w = _from_counts(tot, "strict"), _from_counts(tot, "widened")
        res[m] = (s["f1"], w["f1"])
        print(f"{m:14s} {s['f1']:9.3f} {w['f1']:10.3f} {w['accuracy']:8.3f} {w['md']:5d}")
    if res:
        bs, bw = max(r[0] for r in res.values()), max(r[1] for r in res.values())
        ms = sum(r[0] for r in res.values()) / len(res)
        mw = sum(r[1] for r in res.values()) / len(res)
        best = max(res, key=lambda k: res[k][1])
        print("-" * len(hdr))
        print(f"{'Jansen best':14s} {bs:9.3f} {bw:10.3f}   ({best})")
        print(f"{'Jansen mean':14s} {ms:9.3f} {mw:10.3f}")


def main() -> int:
    # Ng: our TADS2004 vs Jansen's TADS2003 — different year label, not assumed equal -> excluded.
    run("Ng2023", goldlib_ng, NG_COL, _fake_target_ng, set(goldlib_ng.PAPER_TO_KEYS))
    # Vu: Stuber2019 <-> Stüber2019 resolved by accent folding.
    run("Vu2023", goldlib_vu, VU_COL, _fake_target_vu, set(goldlib_vu.AUTHOR_MAP))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
