"""Gold + classification for the Buecker 2023 dashboard (subjective well-being across the life span).

Adapter over ``scripts/score_buecker_ced.py``: the six study-level descriptors Jansen et
al. (2025) benchmarked, gold from Buecker's own supplementary coding
(``eval/buecker2023/gold_payload_100.csv`` via ``validate_buecker_vs_jansen``). Studies
without gold render neutral.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from eval._dashboard.common import CellEval, GoldNotAvailable
from eval._paths import run_dir

REPO = Path(__file__).resolve().parents[2]

RUNS = run_dir("jansen_buecker2023_v6")
MA_NAME = "Buecker 2023"
GOLD_LABEL = "Buecker et al. (2023) supplementary coding (6 study-level descriptors)"
SCHEMA_DIR = REPO / "schemas" / "buecker2023"
RULE_GLOBS = ("estimate_yeart1_from_pubyear", "infer_ethnicity_from_country")
EVAL_MAP = REPO / "eval" / "buecker2023" / "gold_errata.md"
EVALUATED_FIELDS = ("yearT1", "country", "Outcome_variable", "sample_type", "ethnicity", "lag")

_SBU = None
_GOLD = None


def _scorer():
    global _SBU, _GOLD
    if _SBU is None:
        spec = importlib.util.spec_from_file_location(
            "score_buecker_ced", str(REPO / "scripts" / "score_buecker_ced.py"))
        sbu = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sbu)
        _SBU, _GOLD = sbu, sbu.load_gold_descriptors()
    return _SBU, _GOLD


def evaluate(paper_id: str, field: str, target: dict) -> CellEval:
    sbu, gold = _scorer()
    if field not in EVALUATED_FIELDS or paper_id not in gold:
        raise GoldNotAvailable(paper_id)
    k = sbu.classify_cell(field, gold[paper_id].get(field), target.get(field))
    if k is None:
        raise GoldNotAvailable(field)
    g = gold[paper_id].get(field)
    disp = ", ".join(str(x) for x in g) if isinstance(g, (list, set, tuple)) else json.dumps(g, default=str)
    return CellEval(k, disp, "Buecker 2023 supplementary coding")
