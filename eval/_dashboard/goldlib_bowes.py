"""Gold + classification for the Bowes 2023 dashboard (conspiratorial ideation correlates).

Bowes was NOT run through the section-level DCR pipeline: ``scripts/extract_bowes.py``
reads each paper once (Marker prose + table grids + table images) and writes one
``extraction.json`` with study-level fields, per-sample fields and one row per effect
size. This adapter turns that file into the dashboard's cell model (``load_target``) and
scores it with ``scripts/score_bowes_ced.py``'s ``evaluate`` — the nine fields Jansen et
al. (2025) coded. Gold = Bowes' supplementary data, ``eval/bowes2023/gold_*.csv``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from eval._dashboard.common import CellEval, GoldNotAvailable
from eval._paths import run_dir

REPO = Path(__file__).resolve().parents[2]

RUNS = run_dir("jansen_bowes2023")
PAPER_FILE = "extraction.json"
MA_NAME = "Bowes 2023 (single-pass extractor)"
GOLD_LABEL = "Bowes et al. (2023) supplementary data (sample-level descriptors + per-effect-size r, N)"
SCHEMA_DIR = REPO / "schemas" / "bowes2023"
RULE_GLOBS = ()
EVAL_MAP = REPO / "eval" / "bowes2023" / "bowes_references_gold.md"
# extract_bowes.py carries its prompt in code; schemas/bowes2023/prompts.yaml was not used.
ASSET_FILES = (
    ("Extractor (prompt + wire schema are in this script)", REPO / "scripts" / "extract_bowes.py"),
    ("Schema & field definitions", SCHEMA_DIR / "fields.json"),
    ("Jansen's effect-size prompt (kept for ablation, not used)",
     SCHEMA_DIR / "jansen_effectsize_prompt.txt"),
)
EVALUATED_FIELDS = ("YearOfPub", "CTType", "COVID", "Females", "SampleType",
                    "Outcome", "outcome_es", "es_es", "N_es")

_SBW = None
_GOLD = None
_RAW: dict[str, dict] = {}


def _scorer():
    global _SBW, _GOLD
    if _SBW is None:
        import pandas as pd

        spec = importlib.util.spec_from_file_location(
            "score_bowes_ced", str(REPO / "scripts" / "score_bowes_ced.py"))
        sbw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sbw)
        _SBW, _GOLD = sbw, (pd.read_csv(sbw.GS), pd.read_csv(sbw.GE))
    return _SBW, _GOLD


def load_target(paper_dir: Path) -> tuple[dict, dict] | None:
    """Flatten extraction.json into {field: display value} + a paper_rich-like evidence dict."""
    f = paper_dir / PAPER_FILE
    if not f.exists():
        return None
    e = json.loads(f.read_text(encoding="utf-8"))
    _RAW[paper_dir.name] = e
    study, samples, es = e.get("study") or {}, e.get("samples") or [], e.get("effect_sizes") or []

    def lab(s, i):
        return s.get("sample_label") or f"sample {i + 1}"

    target = {
        "YearOfPub": study.get("YearOfPub"),
        "CTType": study.get("CTType"),
        "COVID": study.get("COVID"),
        "Females": {lab(s, i): s.get("female_pct") for i, s in enumerate(samples)},
        "SampleType": {lab(s, i): s.get("recruitment") for i, s in enumerate(samples)},
        "Outcome": sorted({r.get("outcome") for r in es if r.get("outcome")}),
        "outcome_es": [r.get("outcome") for r in es],
        "es_es": {f"{r.get('outcome')} ({r.get('sample_label') or ''})".strip(): r.get("es") for r in es},
        "N_es": {f"{r.get('outcome')} ({r.get('sample_label') or ''})".strip(): r.get("N") for r in es},
        "conspiracy_measure": e.get("conspiracy_measure"),
    }
    ev = [{"quote": str(r.get("evidence") or ""), "section_id": f"{r.get('outcome')}: r={r.get('es')}, N={r.get('N')}",
           "page": None} for r in es if r.get("evidence")]
    rich = {"fields": {f: {"paper_value": {"evidence": ev}} for f in ("Outcome", "outcome_es", "es_es", "N_es")}}
    return target, rich


def _gold_display(field: str, gsub, ge_p) -> str:
    g = gsub.iloc[0]
    if field in ("YearOfPub", "COVID"):
        return str(g[field])
    if field == "CTType":
        return ", ".join(sorted(set(gsub["CTType"].dropna())))
    if field == "SampleType":
        return ", ".join(str(x) for x in gsub["SampleType"].dropna())
    if field == "Females":
        return ", ".join(f"{x:g}%" for x in gsub["Females_pct"].dropna())
    if field == "Outcome":
        return ", ".join(sorted({t for s in gsub["outcomes"].dropna() for t in str(s).split("|") if t}))
    if field == "outcome_es":
        return ", ".join(ge_p["outcome"])
    if field == "es_es":
        return "; ".join(f"{r.outcome}={r.es}" for r in ge_p.itertuples())
    return "; ".join(f"{r.outcome}: N={r.N}" for r in ge_p.itertuples())


def evaluate(paper_id: str, field: str, target: dict) -> CellEval:
    sbw, (gs, ge) = _scorer()
    if field not in EVALUATED_FIELDS or paper_id not in _RAW:
        raise GoldNotAvailable(field)
    gsub, ge_p = gs[gs.paper_id == paper_id], ge[ge.paper_id == paper_id]
    if gsub.empty:
        raise GoldNotAvailable(paper_id)
    k = sbw.evaluate(paper_id, field, _RAW[paper_id], gsub, ge_p)
    if k is None:
        raise GoldNotAvailable(field)
    return CellEval(k, _gold_display(field, gsub, ge_p), "Bowes 2023 supplementary data")
