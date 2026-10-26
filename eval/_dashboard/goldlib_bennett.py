"""Gold + classification for the Bennett 2023 dashboard (male suicide meta-synthesis).

Thin adapter over ``scripts/score_bennett_ced.py`` so the dashboard shows exactly the
cells that scorer counts: gold = Jansen et al. (2025) ``d_long`` labels, four set-valued
fields, ``classify_set``. Papers whose study label cannot be matched to the gold
(or fields without a reference) raise GoldNotAvailable and render neutral.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from eval._dashboard.common import CellEval, GoldNotAvailable, classify_set
from eval._paths import run_dir

REPO = Path(__file__).resolve().parents[2]

RUNS = [run_dir(d) for d in ("jansen_bennett2023_v5", "jansen_bennett2023_new10",
                             "jansen_bennett2023_rest43")]
MA_NAME = "Bennett 2023"
GOLD_LABEL = "Jansen et al. (2025) d_long.xlsx labels (study-level, 4 categorical variables)"
SCHEMA_DIR = REPO / "schemas" / "bennett2023"
RULE_GLOBS = ("bennett*",)
EVAL_MAP = REPO / "eval" / "bennett2023" / "README.md"
EVALUATED_FIELDS = ("Country", "Population", "Type", "Area")

_SB = None
_GOLD = None


def _scorer():
    global _SB, _GOLD
    if _SB is None:
        spec = importlib.util.spec_from_file_location(
            "score_bennett_ced", str(REPO / "scripts" / "score_bennett_ced.py"))
        sb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sb)
        dl = sb.vb.load_d_long()
        _SB = sb
        _GOLD = (dl, {sb._key(s): s for s in dl["study"].dropna().unique()})
    return _SB, _GOLD


def evaluate(paper_id: str, field: str, target: dict) -> CellEval:
    sb, (dl, gold_by_key) = _scorer()
    if field not in EVALUATED_FIELDS:
        raise GoldNotAvailable(field)
    study = sb._match(paper_id, gold_by_key)
    if study is None:
        raise GoldNotAvailable(paper_id)
    ref = sb.vb.gold_set(dl, study, field, field)
    if not ref:
        raise GoldNotAvailable(field)
    got = (sb.vb.norm_set(sb.vb.extract_value(target, field) or "", field) if field == "Country"
           else sb.vb.norm_set(sb.vb.extract_set(target, field), field))
    return CellEval(classify_set(ref, got), ", ".join(sorted(ref)), "d_long.xlsx (Jansen 2025)")
