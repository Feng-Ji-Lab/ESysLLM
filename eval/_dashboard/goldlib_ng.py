"""Ng 2023 gold loading + per-field classification for the evaluation dashboard.

Reference (gold) = the authors' own coding, composited across sources because
no single Ng file exposes every variable:

  IPT       <- unimeta.csv                (Ng's univariate dataset; IPT only)
  Source    <- MeasureCharacteristics.xlsx (Ng's per-measure coding)
  MedCat    <- MeasureCharacteristics.xlsx
  male_pct  <- d_long.xlsx 'male'         (Ng's files don't expose it)
  dxgive    <- d_long.xlsx 'dxgive'       (Ng's files don't expose it)

Each (paper, field) is classified into exact / contains / wrong / missing
(see common.py). Match rules mirror scripts/validate_ng_vs_jansen.py:

  IPT       - set equality (exact); reference subset of ours (contains)
  male_pct  - all sub-studies within +/-2.0 pp (exact); some within tol (contains)
  dxgive    - exact category (exact); gold present among arms with extras (contains)
  Source    - set equality (exact); reference subset of ours (contains)
  MedCat    - set equality (exact); reference subset of ours (contains), case-normalized
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from .common import CellEval, GoldNotAvailable, classify_set

REPO = Path(__file__).resolve().parents[2]
from eval._paths import JANSEN_DIR, run_dir  # shipped locations of runs + third-party gold
D_LONG = JANSEN_DIR / "osfstorage-archive" / "Archive" / "analysis" / "d_long.xlsx"
MC = JANSEN_DIR / "Ng2023_34" / "Study Measure ES Data" / "MeasureCharacteristics.xlsx"
UNIMETA = JANSEN_DIR / "Ng2023_34" / "Univariate" / "unimeta.csv"
RUNS = run_dir("jansen_ng2023")
MA_NAME = "Ng 2023"
GOLD_LABEL = "Ng own coding (unimeta + MeasureCharacteristics) + d_long"

# Customizable-asset locations for this meta-analysis (shown in the dashboard).
SCHEMA_DIR = REPO / "schemas" / "ng2023"
RULE_GLOBS = ("ng_*", "ng2023")  # under rules/
EVAL_MAP = REPO / "eval" / "ng2023" / "groundtruth_map.yaml"

MALE_TOL = 2.0
EVALUATED_FIELDS = ("IPT", "male_pct", "dxgive", "Source", "MedCat")

# paper_id (PDF stem) -> (d_long study key, ESdata studyid)
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

SOURCE_LABEL = "MeasureCharacteristics.xlsx (Ng)"
MEDCAT_LABEL = "MeasureCharacteristics.xlsx (Ng)"
IPT_LABEL = "unimeta.csv (Ng)"
DLONG_LABEL = "d_long.xlsx"


@lru_cache(maxsize=1)
def _d_long() -> pd.DataFrame:
    df = pd.read_excel(D_LONG)
    return df[df["meta"] == "Ng2023"].copy()


@lru_cache(maxsize=1)
def _mc() -> pd.DataFrame:
    df = pd.read_excel(MC)
    df["MedCat"] = df["MedCat"].astype(str).str.strip().str.lower()
    df["Source"] = df["Source"].astype(int)
    return df


@lru_cache(maxsize=1)
def _unimeta() -> pd.DataFrame:
    return pd.read_csv(UNIMETA, encoding="latin-1")


def _d_long_value(study: str, var: str) -> str:
    sub = _d_long()[(_d_long()["study"] == study) & (_d_long()["var"] == var)]
    codes = sub["code"].astype(str).str.strip().unique().tolist()
    return codes[0] if codes else ""


# -- extracted-side helpers (per-cell {key: [vals]} shape) -------------------


def _per_sample(target: dict, field: str) -> dict[str, str]:
    out: dict[str, str] = {}
    v = target.get(field)
    if isinstance(v, dict):
        for sk, cell in v.items():
            if isinstance(cell, list) and cell and cell[0] not in (None, "None", ""):
                out[sk] = str(cell[0])
    return out


def _flat_set(target: dict, field: str) -> set[str]:
    v = target.get(field)
    out: set[str] = set()

    def add(entry):
        if isinstance(entry, list):
            out.update(str(c).strip().lower() for c in entry if c not in (None, "None"))
        elif entry not in (None, "None", ""):
            out.add(str(entry).strip().lower())

    if isinstance(v, dict):
        for cell in v.values():
            if isinstance(cell, list):
                for entry in cell:
                    add(entry)
    elif isinstance(v, list):
        for entry in v:
            add(entry)
    return out


def _classify_male(gv: float, extracted: list[float]) -> str:
    if not extracted:
        return "missing"
    within = [e for e in extracted if abs(e - gv) <= MALE_TOL]
    if not within:
        return "wrong"
    return "exact" if len(within) == len(extracted) else "contains"


def _fmt_num(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def evaluate(paper_id: str, field: str, target: dict) -> CellEval:
    if field not in EVALUATED_FIELDS or paper_id not in PAPER_TO_KEYS:
        raise GoldNotAvailable
    study_key, studyid = PAPER_TO_KEYS[paper_id]

    if field == "IPT":
        truth = {
            str(x) for x in _unimeta()[_unimeta()["studyid"] == studyid]["IPT"].astype(int).unique()
        }
        if not truth:
            raise GoldNotAvailable
        ours = {str(v) for v in _per_sample(target, "IPT").values()}
        disp = "{" + ", ".join(sorted(truth)) + "}"
        return CellEval(classify_set(truth, ours), disp, IPT_LABEL)

    if field == "male_pct":
        gold_raw = _d_long_value(study_key, "male")
        try:
            gv = float(str(gold_raw).replace(",", "."))
        except (TypeError, ValueError):
            raise GoldNotAvailable from None
        extracted: list[float] = []
        for v in _per_sample(target, "male_pct").values():
            try:
                extracted.append(float(v))
            except (TypeError, ValueError):
                continue
        return CellEval(_classify_male(gv, extracted), f"{_fmt_num(gv)}% (±2pp)", DLONG_LABEL)

    if field == "dxgive":
        gold = _d_long_value(study_key, "dxgive").strip()
        if not gold:
            raise GoldNotAvailable
        ours = {str(v).strip() for v in _per_sample(target, "dxgive").values()}
        return CellEval(classify_set({gold}, ours), gold, DLONG_LABEL)

    if field == "Source":
        truth = {str(x) for x in _mc()[_mc()["studyid"] == studyid]["Source"].unique()}
        if not truth:
            raise GoldNotAvailable
        ours = _flat_set(target, "Source")
        disp = "{" + ", ".join(sorted(truth)) + "}"
        return CellEval(classify_set(truth, ours), disp, SOURCE_LABEL)

    # MedCat
    truth = {str(x).strip().lower() for x in _mc()[_mc()["studyid"] == studyid]["MedCat"].dropna()}
    truth = {x for x in truth if x not in ("nan", "none", "")}
    if not truth:
        raise GoldNotAvailable
    ours = {x.lower() for x in _flat_set(target, "MedCat")}
    disp = "{" + ", ".join(sorted(truth)) + "}"
    return CellEval(classify_set(truth, ours), disp, MEDCAT_LABEL)
