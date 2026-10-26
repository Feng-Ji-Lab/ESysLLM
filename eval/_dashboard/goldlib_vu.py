"""Vu 2024 gold loading + per-field classification for the evaluation dashboard.

Reference (gold) source: ``Jansen2025/Vu2023_15/All_data/WI_meta.csv`` — Vu's
own hand-coding, one row per (Tmt x Ctr) cell. We deliberately avoid Jansen's
``d_long.xlsx`` here because it has documented paper-swap bugs for several Vu
papers (see docs/reports/2026-05-30-jansen-gold-vs-wi-meta.md).

Each (paper, field) is classified into exact / contains / wrong / missing (see
common.py). Match rules mirror scripts/validate_vu_vs_wi_meta.py:

  Design   - exact lowercase string match
  country  - exact lowercase, US variants normalized
  info_cost - numeric tolerance +/-0.011
  N_*_CI_* - multiset equality (exact); reference sub-multiset of ours (contains)
"""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .common import CellEval, GoldNotAvailable, classify_multiset, classify_scalar

REPO = Path(__file__).resolve().parents[2]
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
WI = JANSEN_DIR / "Vu2023_15" / "All_data" / "WI_meta.csv"
RUNS = run_dir("jansen_vu2024")
GOLD_LABEL = "WI_meta.csv (Vu's own coding)"
MA_NAME = "Vu 2024"

# Customizable-asset locations for this meta-analysis (shown in the dashboard).
SCHEMA_DIR = REPO / "schemas" / "vu2024"
RULE_GLOBS = ("vu_*", "vu2024")  # under rules/
EVAL_MAP = REPO / "eval" / "vu2024" / "groundtruth_map.yaml"

SCALAR_FIELDS = ("Design", "country", "info_cost")
N_FIELDS = ("N_Self_CI_Tmt", "N_Self_CI_Ctr", "N_Altr_CI_Ctr")
EVALUATED_FIELDS = (*SCALAR_FIELDS, *N_FIELDS)

# paper_id -> (author substring, year) used to find WI_meta rows.
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


@lru_cache(maxsize=1)
def _load_wi() -> pd.DataFrame:
    df = pd.read_csv(WI)
    df.columns = [c.strip() for c in df.columns]
    return df


def _wi_rows(paper: str) -> pd.DataFrame:
    author, year = AUTHOR_MAP[paper]
    wi = _load_wi()
    return wi[wi["Authors"].str.contains(author, na=False, regex=False) & (wi["year"] == year)]


def _wi_scalar(paper: str, col: str) -> str | None:
    vals = _wi_rows(paper)[col].dropna().unique().tolist()
    return str(vals[0]) if vals else None


def _wi_n_multiset(paper: str, var: str) -> Counter:
    return Counter(int(x) for x in _wi_rows(paper)[var].dropna())


def _norm_country(s: str) -> str:
    s = (s or "").strip().lower()
    return {"us": "united states", "usa": "united states"}.get(s, s)


def _ours_n_multiset(target: dict, field: str) -> Counter:
    """Multiset of integer cell values from the per-cell ``{key: [ints]}`` shape."""
    obj = target.get(field, {})
    if not isinstance(obj, dict):
        return Counter()
    out: list[int] = []
    for cell in obj.values():
        if isinstance(cell, list):
            out.extend(x for x in cell if isinstance(x, int))
    return Counter(out)


def _fmt_num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def evaluate(paper_id: str, field: str, target: dict) -> CellEval:
    """Classify one (paper, field), or raise GoldNotAvailable.

    ``target`` is the paper's parsed paper_target.json.
    """
    if field not in EVALUATED_FIELDS or paper_id not in AUTHOR_MAP:
        raise GoldNotAvailable

    if field in ("Design", "country"):
        norm = _norm_country if field == "country" else (lambda s: (s or "").strip().lower())
        truth = norm(_wi_scalar(paper_id, field) or "")
        if not truth:
            raise GoldNotAvailable
        ours = norm(target.get(field) or "")
        klass = classify_scalar(matched=ours == truth, extracted_present=bool(ours))
        return CellEval(klass, truth, GOLD_LABEL)

    if field == "info_cost":
        try:
            truth_v = float(_wi_scalar(paper_id, "info_cost"))
        except (TypeError, ValueError):
            raise GoldNotAvailable from None
        try:
            ours_v = float(target.get("info_cost"))
        except (TypeError, ValueError):
            ours_v = None
        klass = classify_scalar(
            matched=ours_v is not None and abs(ours_v - truth_v) <= 0.011,
            extracted_present=ours_v is not None,
        )
        return CellEval(klass, _fmt_num(truth_v), GOLD_LABEL)

    # N_*_CI_* multiset fields
    truth_c = _wi_n_multiset(paper_id, field)
    ours_c = _ours_n_multiset(target, field)
    gold_display = str(sorted(truth_c.elements())) if truth_c else "[] (NA)"
    klass = classify_multiset(truth_c, ours_c)
    return CellEval(klass, gold_display, GOLD_LABEL)
