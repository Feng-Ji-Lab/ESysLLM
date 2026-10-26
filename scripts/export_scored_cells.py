"""Export every scored (paper x field) item of all nine meta-analyses to CSV.

One long-format file per meta-analysis, ``results/<ma>/scored_cells.csv``, with the
same columns everywhere, so the three native output formats (v1 ``final_results.json``,
v2 ``paper_target.json`` + ``paper_rich.json``, Bowes ``extraction.json``) can be read
side by side in R or Python and feed ``scripts/build_summary.py`` and the dashboards.

The classification is NOT re-implemented here. Each block calls the exact code the
paper's numbers came from:

* He2020 (Study 3, Appendix D) and the three Study-4 datasets: ``legacy/v1/src/validator.py``
  (``_values_subset``, abs tol 0.05) through the same loop as
  ``legacy/v1/validation/calculate_metrics.py``; exact-vs-contains is taken from
  ``legacy/v1/validation/build_dashboard.compare_field`` (full / partial).
* Vu, Ng: ``eval._dashboard.build_dashboard.build``.
* Bennett / Bowes / Buecker: ``scripts/score_{bennett,bowes,buecker}_ced.py``.

Match classes: exact | contains | wrong | missing.  ``correct_coverage`` (the paper's
standard: the reference value(s) appear in the extraction, extras allowed) is
exact|contains; ``correct_strict`` is exact only.

Usage:  PYTHONPATH=.:src python scripts/export_scored_cells.py [--only vu2024 ...]
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "src", REPO / "scripts"):
    sys.path.insert(0, str(p))

from eval._paths import RESULTS_DIR, run_dir  # noqa: E402

COLUMNS = [
    "ma", "study", "pipeline", "model", "temperature", "paper_id", "field", "sample_key",
    "extracted_value", "reference_value", "match_class", "correct_coverage",
    "correct_strict", "evidence_location", "evidence_quote", "scorer",
]
MAXQ = 300  # evidence quote truncation


def _row(**kw) -> dict:
    k = kw["match_class"]
    kw["correct_coverage"] = int(k in ("exact", "contains"))
    kw["correct_strict"] = int(k == "exact")
    kw["evidence_quote"] = (kw.get("evidence_quote") or "")[:MAXQ]
    for c in COLUMNS:
        kw.setdefault(c, "")
    return {c: kw[c] for c in COLUMNS}


def _j(v) -> str:
    """Compact, deterministic text for a value of any shape."""
    if isinstance(v, (set, frozenset)):
        v = sorted(v)
    if isinstance(v, Counter):
        v = sorted(v.elements())
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, str(REPO / "scripts" / f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _v2_evidence(paper_dir: Path, field: str) -> tuple[str, str]:
    """(location, quote) of the first evidence item for a v2 field, or a derivation tag."""
    rich = paper_dir / "paper_rich.json"
    if not rich.exists():
        return "", ""
    f = (json.loads(rich.read_text()).get("fields") or {}).get(field) or {}
    vals = [f.get("paper_value")] if f.get("paper_value") else []
    for cell in (f.get("cells") or {}).values():
        vals.extend(cell if isinstance(cell, list) else [cell])
    for v in vals:
        if not isinstance(v, dict):
            continue
        d = v.get("derivation")
        if d and d.get("skill_name"):
            return f"derived:{d['skill_name']}", _j(d.get("inputs") or {})
        for e in v.get("evidence") or []:
            loc = e.get("block_id") or e.get("section_id") or ""
            if e.get("page") is not None:
                loc = f"{loc} p{e['page']}"
            return loc.strip(), e.get("quote") or ""
    return "", ""


# ---------------------------------------------------------------------------
# v1 (legacy) — He2020 and the three Study-4 datasets
# ---------------------------------------------------------------------------
LEGACY = REPO / "legacy" / "v1"


_LEGACY_CACHE: tuple | None = None


def _legacy_modules():
    """Import legacy/v1's Validator and dashboard module once (they chdir and print)."""
    global _LEGACY_CACHE
    if _LEGACY_CACHE is not None:
        return _LEGACY_CACHE
    sys.path.insert(0, str(LEGACY))
    from src.validator import Validator  # noqa: E402

    spec = importlib.util.spec_from_file_location(
        "legacy_dash", str(LEGACY / "validation" / "build_dashboard.py"))
    dash = importlib.util.module_from_spec(spec)
    cwd = os.getcwd()
    os.chdir(LEGACY)  # the legacy modules resolve config/ relative to the repo root
    try:
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):  # "settings.json missing" notice
            spec.loader.exec_module(dash)
    finally:
        os.chdir(cwd)
    _LEGACY_CACHE = (Validator, dash)
    return _LEGACY_CACHE


def _v1_is_correct(validator, gt_vals, ext_vals) -> bool:
    """Verbatim decision logic of legacy/v1/validation/calculate_metrics.py."""
    if isinstance(gt_vals, dict) and "male" in gt_vals:
        if not isinstance(ext_vals, dict):
            if isinstance(ext_vals, list):
                ext_vals = {"male": [], "female": [], "total": ext_vals}
        normalized_gt = {
            g: validator._flatten_values(gt_vals.get(g, []))
            for g in ("male", "female", "total", "other")
        }
        for gender in ("male", "female", "total"):
            gt_g_list = normalized_gt.get(gender, [])
            if validator._is_gt_empty(gt_g_list):
                continue
            gt_scalars = validator._flatten_to_scalars(gt_g_list)
            ext_g_list = ext_vals.get(gender, []) if isinstance(ext_vals, dict) else []
            if not validator._values_subset(gt_scalars, ext_g_list):
                return False
        return True
    gt_scalars = validator._flatten_to_scalars(gt_vals)
    if not isinstance(ext_vals, list):
        ext_vals = [ext_vals]
    return validator._values_subset(gt_scalars, ext_vals)


def rows_v1(*, ma: str, study: str, model: str, temperature: str, output_dir: Path,
            gt_path: Path, target_fields: list[str], papers: list[str] | None,
            scorer: str) -> list[dict]:
    Validator, dash = _legacy_modules()
    validator = Validator(str(gt_path), code_book_path=str(LEGACY / "config" / "code_book.json"),
                         threshold=0.05, target_fields=target_fields)
    names = sorted(d for d in os.listdir(output_dir) if (output_dir / d).is_dir())
    if papers is not None:
        names = [n for n in names if n in papers]
    out = []
    for paper in names:
        res_path = output_dir / paper / "final_results.json"
        try:
            final_results = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
        except json.JSONDecodeError:
            final_results = {}
        gt_data = validator.get_ground_truth_for_paper(paper)
        if not gt_data:
            continue
        organized = validator._normalize_extracted(final_results)
        for gt_field, gt_vals in gt_data.items():
            if gt_field in ("ID", "filename"):
                continue
            ext_field = validator.key_mapping.get(gt_field, gt_field)
            if validator.target_fields and ext_field not in validator.target_fields:
                continue
            if validator._is_gt_empty(gt_vals):
                continue
            fr = final_results.get(ext_field) or {}
            if ext_field not in organized:
                klass, ext_repr = "missing", ""
            else:
                ext_vals = organized[ext_field]
                ext_repr = _j(ext_vals)
                if _v1_is_correct(validator, gt_vals, ext_vals):
                    full = dash.compare_field(ext_field, fr, gt_vals) == "full" if fr else False
                    klass = "exact" if full else "contains"
                else:
                    klass = "wrong"
            idx = fr.get("best_indices")
            out.append(_row(
                ma=ma, study=study, pipeline="v1", model=model, temperature=temperature,
                paper_id=paper, field=ext_field, sample_key="paper",
                extracted_value=ext_repr, reference_value=_j(gt_vals), match_class=klass,
                evidence_location=f"candidates {idx}" if idx else "",
                evidence_quote=fr.get("reason") or "", scorer=scorer))
    return out


def export_v1_all() -> dict[str, list[dict]]:
    he_targets = json.loads((LEGACY / "config" / "settings.example.json").read_text())["validation_targets"]
    he_gt = LEGACY / "test" / "ground_truth.json"
    models = {"gemini_2.5_flash": ("gemini-2.5-flash", "gemini-2.5-flash"),
              "gpt_5_mini": ("gpt-5-mini", "gpt-5-mini"),
              "claude_haiku_4.5": ("claude-haiku-4.5", "claude-haiku-4-5")}
    temp_papers = ["1Atari2016", "1Benford2014", "1Cotter2015", "1Iannantuono2012", "1Swami2009check"]
    he_rows: list[dict] = []
    for d, (model, tdir) in models.items():
        he_rows += rows_v1(ma="he2020", study="Study 3", model=model, temperature="0",
                           output_dir=LEGACY / "output" / d, gt_path=he_gt, target_fields=he_targets,
                           papers=None, scorer="legacy/v1/validation/calculate_metrics.py")
        for t in ("0.2", "0.4"):
            he_rows += rows_v1(ma="he2020", study="Appendix D", model=model, temperature=t,
                               output_dir=LEGACY / "output_temp_diff" / f"{tdir}_{t}", gt_path=he_gt,
                               target_fields=he_targets, papers=temp_papers,
                               scorer="legacy/v1/validation/calculate_temp_metrics.py")
    # Appendix D's T=0 bars are the Study-3 runs restricted to the same five papers
    # (calculate_temp_metrics.py reads them from output/<model>); no separate rows needed.

    goal_targets = json.loads((LEGACY / "goal_orientation_and_performance_adaptation" / "settings.json")
                              .read_text())["validation_targets"]
    s4 = {
        "goal_orientation_2019": ("goal_orientation_and_performance_adaptation",
                                  LEGACY / "goal_orientation_and_performance_adaptation" / "output" / "gemini_2.5_flash",
                                  goal_targets, "legacy/v1/validation/check_13_papers.py"),
        "gratitude_loneliness_2024": ("meta_gratitude_loneliness",
                                      LEGACY / "meta_gratitude_loneliness" / "output",
                                      ["r", "N", "female", "M_age", "SD_age", "usa_vs_other"],
                                      "legacy/v1/validation/temp_calc_metrics.py"),
        "intelligence_creativity_2021": ("meta_intelligence", LEGACY / "meta_intelligence" / "output",
                                         ["SAMPLE SIZE", "ES", "Mage", "IQ modality", "IQ Aspect",
                                          "Creativity Measures", "Domain classified"],
                                         "legacy/v1/validation/temp_calc_metrics.py"),
    }
    out = {"he2020": he_rows}
    for ma, (d, outdir, targets, scorer) in s4.items():
        out[ma] = rows_v1(ma=ma, study="Study 4", model="gemini-2.5-flash", temperature="0",
                          output_dir=outdir, gt_path=LEGACY / d / "ground_truth.json",
                          target_fields=targets, papers=None, scorer=scorer)
    return out


# ---------------------------------------------------------------------------
# v2 — Vu / Ng via the dashboard builder
# ---------------------------------------------------------------------------
def export_dashboard_ma(ma: str, key: str) -> list[dict]:
    from eval._dashboard.build_dashboard import build

    data = build(key)
    runs = run_dir({"vu": "jansen_vu2024", "ng": "jansen_ng2023"}[key])
    out = []
    for p in data["papers"]:
        for field, cell in p["cells"].items():
            if cell.get("klass") not in ("exact", "contains", "wrong", "missing"):
                continue  # 'neutral' = displayed but unscored
            if cell.get("kind") == "scalar":  # paper-level field: {'text': ...}
                rows, sample = cell.get("text", ""), "paper"
            else:  # per-sample field: {'rows': [[sample_label, [values]], ...]}
                rows = cell.get("rows") or []
                sample = rows[0][0] if len(rows) == 1 else ("multi" if rows else "")
            ev = (cell.get("evidence") or [{}])[0]
            loc = ev.get("section") or ""
            if ev.get("page") is not None:
                loc = f"{loc} p{ev['page']}"
            out.append(_row(
                ma=ma, study="Study 5", pipeline="v2", model="gemini-2.5-flash", temperature="0",
                paper_id=p["id"], field=field, sample_key=sample,
                extracted_value=_j(rows), reference_value=str(cell.get("gold", "")),
                match_class=cell["klass"], evidence_location=loc.strip(),
                evidence_quote=ev.get("quote") or "", scorer="eval/_dashboard/build_dashboard.py"))
    _ = runs
    return out


# ---------------------------------------------------------------------------
# v2 — Bennett / Buecker via their scorers; Bowes via its single-pass scorer
# ---------------------------------------------------------------------------
def export_bennett() -> list[dict]:
    sb = _load_script("score_bennett_ced")
    vb = sb.vb
    dl = vb.load_d_long()
    gold_by_key = {sb._key(s): s for s in dl["study"].dropna().unique()}
    out = []
    for d in sb.RUN_DIRS:
        p = run_dir(d)
        if not p.exists():
            continue
        for s in sorted(p.iterdir()):
            pt = s / "paper_target.json"
            if not pt.exists():
                continue
            study = sb._match(s.name, gold_by_key)
            if study is None:
                continue
            e = json.loads(pt.read_text())
            for f in sb.FIELDS:
                ref = vb.gold_set(dl, study, f, f)
                if not ref:
                    continue
                got = (vb.norm_set(vb.extract_value(e, f) or "", f) if f == "Country"
                       else vb.norm_set(vb.extract_set(e, f), f))
                loc, q = _v2_evidence(s, f)
                out.append(_row(
                    ma="bennett2023", study="Study 5", pipeline="v2", model="gemini-2.5-flash",
                    temperature="0", paper_id=s.name, field=f, sample_key="paper",
                    extracted_value=_j(got), reference_value=_j(ref),
                    match_class=sb.classify_set(ref, got), evidence_location=loc,
                    evidence_quote=q, scorer="scripts/score_bennett_ced.py"))
    return out


def export_buecker() -> list[dict]:
    sbu = _load_script("score_buecker_ced")
    gold = sbu.load_gold_descriptors()
    out = []
    for st in sbu.STUDIES:
        ext = sbu._extracted(st)
        if ext is None or st not in gold:
            continue
        for f in sbu.FIELDS:
            k = sbu.classify_cell(f, gold[st].get(f), ext.get(f))
            if k is None:
                continue
            loc, q = _v2_evidence(sbu.RUNS / st, f)
            out.append(_row(
                ma="buecker2023", study="Study 5", pipeline="v2", model="gemini-2.5-flash",
                temperature="0", paper_id=st, field=f, sample_key="paper",
                extracted_value=_j(ext.get(f)), reference_value=_j(gold[st].get(f)),
                match_class=k, evidence_location=loc, evidence_quote=q,
                scorer="scripts/score_buecker_ced.py"))
    return out


def export_bowes() -> list[dict]:
    import pandas as pd

    sbw = _load_script("score_bowes_ced")
    gs, ge = pd.read_csv(sbw.GS), pd.read_csv(sbw.GE)
    papers = sorted(p for p in gs.paper_id.unique() if (sbw.RUNS / p / "extraction.json").exists())

    def reprs(f, e, gsub, ge_p):
        study, samples, es = e.get("study") or {}, e.get("samples") or [], e.get("effect_sizes") or []
        if f in ("YearOfPub", "COVID"):
            return _j(study.get(f)), _j(gsub.iloc[0][f])
        if f == "CTType":
            return _j(study.get("CTType")), _j(sorted(set(gsub["CTType"].dropna())))
        if f == "SampleType":
            return _j([s.get("recruitment") for s in samples]), _j(list(gsub["SampleType"].dropna()))
        if f == "Females":
            return _j([s.get("female_pct") for s in samples]), _j(list(gsub["Females_pct"].dropna()))
        if f == "Outcome":
            return (_j(sorted({r.get("outcome") for r in es if r.get("outcome")})),
                    _j(sorted({t for s in gsub["outcomes"].dropna() for t in str(s).split("|") if t})))
        if f == "outcome_es":
            return _j([r.get("outcome") for r in es]), _j(list(ge_p["outcome"]))
        if f == "es_es":
            return (_j([[r.get("outcome"), r.get("es")] for r in es]),
                    _j([[r.outcome, r.es] for r in ge_p.itertuples()]))
        return (_j([[r.get("outcome"), r.get("N")] for r in es]),
                _j([[r.outcome, r.N] for r in ge_p.itertuples()]))

    out = []
    for p in papers:
        e = json.loads((sbw.RUNS / p / "extraction.json").read_text())
        gsub, ge_p = gs[gs.paper_id == p], ge[ge.paper_id == p]
        es_quotes = " | ".join(str(r.get("evidence") or "") for r in (e.get("effect_sizes") or [])[:5])
        for f in sbw.FIELDS:
            k = sbw.evaluate(p, f, e, gsub, ge_p)
            if k is None:
                continue
            ext_r, ref_r = reprs(f, e, gsub, ge_p)
            out.append(_row(
                ma="bowes2023", study="Study 5", pipeline="v2-singlepass", model="gemini-2.5-flash",
                temperature="0", paper_id=p, field=f,
                sample_key="paper" if f in ("YearOfPub", "COVID", "CTType", "Outcome") else "multi",
                extracted_value=ext_r, reference_value=ref_r, match_class=k,
                evidence_location="extraction.json", evidence_quote=es_quotes if f.endswith("_es") else "",
                scorer="scripts/score_bowes_ced.py"))
    return out


# ---------------------------------------------------------------------------
def _write(ma: str, rows: list[dict]) -> None:
    d = RESULTS_DIR / ma
    d.mkdir(parents=True, exist_ok=True)
    with (d / "scored_cells.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    c = Counter(r["match_class"] for r in rows)
    ced_w = c["exact"] + c["contains"]
    f1w = 2 * ced_w / (2 * ced_w + c["wrong"] + c["missing"]) if rows else 0
    print(f"{ma:30s} rows={len(rows):5d}  {dict(c)}  coverage-F1(all rows)={f1w:.4f}")


EXPORTERS = {
    "vu2024": lambda: export_dashboard_ma("vu2024", "vu"),
    "ng2023": lambda: export_dashboard_ma("ng2023", "ng"),
    "bennett2023": export_bennett,
    "bowes2023": export_bowes,
    "buecker2023": export_buecker,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="*", help="subset of MA keys (v1 keys: he2020, "
                    "goal_orientation_2019, gratitude_loneliness_2024, intelligence_creativity_2021)")
    args = ap.parse_args()
    want = set(args.only or [])
    v1 = export_v1_all() if not want or want & {"he2020", "goal_orientation_2019",
                                                  "gratitude_loneliness_2024",
                                                  "intelligence_creativity_2021"} else {}
    for ma, rows in v1.items():
        if not want or ma in want:
            _write(ma, rows)
    for ma, fn in EXPORTERS.items():
        if not want or ma in want:
            _write(ma, fn())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
