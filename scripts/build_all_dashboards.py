"""Build one HTML dashboard per meta-analysis (and per model / temperature for He2020)
plus an index page, into dashboard/.

v2 pages (Vu, Ng, Bennett, Buecker, Bowes) come from ``eval._dashboard.build_dashboard``;
v1 pages (He2020 x 3 models x {0, 0.2, 0.4}, Goal Orientation, Gratitude-Loneliness,
Intelligence-Creativity) come from ``legacy/v1/validation/build_dashboard.py`` called as a
library, with the dataset's validation targets injected (the legacy script otherwise reads
them from a gitignored config/settings.json).

Every page is checked against results/<ma>/scored_cells.csv before it is written:
- v2: the page's widened/strict F1 must equal the F1 recomputed from the CSV;
- v1: the page's full / partial / none counts must equal the CSV's exact / contains /
  (wrong + missing) counts.
The index table is computed from the same CSVs (coverage standard = the paper's).

Usage:  PYTHONPATH=.:src python scripts/build_all_dashboards.py [--out dashboard]
"""
from __future__ import annotations

import argparse
import csv
import html
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "src", REPO / "scripts"):
    sys.path.insert(0, str(p))

from build_summary import metrics  # noqa: E402
from eval._paths import RESULTS_DIR  # noqa: E402
from export_scored_cells import LEGACY, _legacy_modules  # noqa: E402

TEMP_PAPERS = ["1Atari2016", "1Benford2014", "1Cotter2015", "1Iannantuono2012", "1Swami2009check"]
V1_MODELS = {"gemini_2.5_flash": ("gemini-2.5-flash", "gemini-2.5-flash"),
             "gpt_5_mini": ("gpt-5-mini", "gpt-5-mini"),
             "claude_haiku_4.5": ("claude-haiku-4.5", "claude-haiku-4-5")}


def _cells(ma: str) -> list[dict]:
    with (RESULTS_DIR / ma / "scored_cells.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _sel(rows, **kw):
    out = rows
    for k, v in kw.items():
        if k == "papers":
            out = [r for r in out if r["paper_id"] in set(v)]
        else:
            out = [r for r in out if r[k] == v]
    return out


# ---------------------------------------------------------------- v2
def build_v2(key: str, ma: str, out: Path) -> dict:
    from eval._dashboard.build_dashboard import build, render_html

    data = build(key)
    s = data["summary"]["overall"]
    m = metrics(_cells(ma), "coverage")
    ms = metrics(_cells(ma), "strict")
    if abs(s["widened"]["f1"] - m["f1"]) > 1e-9 or abs(s["strict"]["f1"] - ms["f1"]) > 1e-9:
        raise SystemExit(f"{ma}: dashboard F1 {s['widened']['f1']:.4f}/{s['strict']['f1']:.4f} "
                         f"!= scored_cells {m['f1']:.4f}/{ms['f1']:.4f}")
    out.write_text(render_html(data), encoding="utf-8")
    return {"n_papers": m["n_papers"], **m}


# ---------------------------------------------------------------- v1
def build_v1(*, ma: str, results_root: Path, gt_path: Path, targets: list[str],
             papers: list[str] | None, csv_rows: list[dict], out: Path) -> dict:
    _, dash = _legacy_modules()
    dash.VALIDATION_TARGETS = list(targets)
    loaded, fields = dash.load_results(str(results_root))
    if papers is not None:
        loaded = {k: v for k, v in loaded.items() if k in set(papers)}
    gt = dash.load_ground_truth(str(gt_path))
    comparison = dash.build_comparison(loaded, fields, gt)
    # Compare on the cells the scorer scored. The legacy page also colours cells whose
    # reference is empty as "full" ("both sides have nothing"); the scorer skips those.
    scored = {(r["paper_id"], r["field"]) for r in csv_rows}
    page = Counter(st for p, per in comparison.items() for f, st in per.items() if (p, f) in scored)
    missing_on_page = scored - {(p, f) for p, per in comparison.items() for f in per}
    extra = [(p, f, st) for p, per in comparison.items() for f, st in per.items()
             if (p, f) not in scored and st != "full"]
    csvc = Counter(r["match_class"] for r in csv_rows)
    want = {"full": csvc["exact"], "partial": csvc["contains"], "none": csvc["wrong"] + csvc["missing"]}
    got = {k: page.get(k, 0) for k in want}
    if got != want or missing_on_page or extra:
        raise SystemExit(f"{ma} ({out.name}): dashboard counts {got} != scored_cells {want}; "
                         f"scored cells absent from page: {sorted(missing_on_page)[:5]}; "
                         f"unscored page cells not 'full': {extra[:5]}")
    html_text = dash.generate_html(loaded, fields, comparison, dash.build_gt_display(gt), gt)
    out.write_text(html_text, encoding="utf-8")
    m = metrics(csv_rows, "coverage")
    return {"n_papers": m["n_papers"], **m}


def _index(rows: list[dict], out: Path) -> None:
    head = ("Meta-analysis", "Paper study", "Pipeline", "Model", "T", "Papers", "Items",
            "Precision", "Recall", "F1 (coverage)", "Dashboard")
    trs = []
    for r in rows:
        link = f'<a href="{html.escape(r["file"])}">{html.escape(r["file"])}</a>'
        cells = (r["ma"], r["study"], r["pipeline"], r["model"], r["temperature"], r["n_papers"],
                 r["n_items"], f"{r['precision']:.4f}", f"{r['recall']:.4f}", f"{r['f1']:.4f}", link)
        trs.append("<tr>" + "".join(f"<td>{c if c == link else html.escape(str(c))}</td>" for c in cells) + "</tr>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESysLLM dashboards</title>
<style>
:root{{--bg:#fff;--fg:#1b1b1b;--line:#d7d7d7;--muted:#5b5b5b;--accent:#0b5fa5}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#121212;--fg:#e8e8e8;--line:#333;--muted:#aaa;--accent:#7ab8ff}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto}} h1{{font-size:1.4rem;margin:0 0 .25rem}} p{{color:var(--muted);margin:.25rem 0 1rem}}
table{{border-collapse:collapse;width:100%;font-size:.92rem}} th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;white-space:nowrap}}
th{{color:var(--muted);font-weight:600}} td:nth-child(n+6){{text-align:right;font-variant-numeric:tabular-nums}} td:last-child{{text-align:left}}
a{{color:var(--accent)}} .wrap{{overflow-x:auto}}
</style></head><body><main>
<h1>ESysLLM extraction dashboards</h1>
<p>One page per meta-analysis (He2020 also per model and temperature). Metrics use the paper's
coverage rule: a reference value counts as recovered when it appears in the extraction.
Numbers are recomputed from <code>results/&lt;ma&gt;/scored_cells.csv</code>; see
<code>results/summary.csv</code> for the mapping to the manuscript.</p>
<div class="wrap"><table><thead><tr>{''.join(f'<th>{h}</th>' for h in head)}</tr></thead>
<tbody>{''.join(trs)}</tbody></table></div>
</main></body></html>"""
    out.write_text(page, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(REPO / "dashboard"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []

    def add(ma, study, pipeline, model, temp, fname, m):
        index.append({"ma": ma, "study": study, "pipeline": pipeline, "model": model,
                      "temperature": temp, "file": fname, **m})

    # --- v1: He2020 per model x temperature
    he = _cells("he2020")
    he_targets = __import__("json").loads((LEGACY / "config" / "settings.example.json").read_text())["validation_targets"]
    for d, (model, tdir) in V1_MODELS.items():
        fname = f"he2020_{model}_t0.html"
        rows = _sel(he, study="Study 3", model=model, temperature="0")
        m = build_v1(ma="he2020", results_root=LEGACY / "output" / d, gt_path=LEGACY / "test" / "ground_truth.json",
                     targets=he_targets, papers=None, csv_rows=rows, out=out / fname)
        add("He2020 (Body Appreciation x BMI)", "Study 3", "v1", model, "0", fname, m)
        for t in ("0.2", "0.4"):
            fname = f"he2020_{model}_t{t.replace('.', '')}.html"
            rows = _sel(he, study="Appendix D", model=model, temperature=t)
            m = build_v1(ma="he2020", results_root=LEGACY / "output_temp_diff" / f"{tdir}_{t}",
                         gt_path=LEGACY / "test" / "ground_truth.json", targets=he_targets,
                         papers=TEMP_PAPERS, csv_rows=rows, out=out / fname)
            add("He2020 (5-paper temperature subset)", "Appendix D", "v1", model, t, fname, m)

    # --- v1: Study 4
    goal_targets = __import__("json").loads((LEGACY / "goal_orientation_and_performance_adaptation" / "settings.json")
                                           .read_text())["validation_targets"]
    s4 = [
        ("goal_orientation_2019", "Goal Orientation & Performance Adaptation (Stasielowicz 2019)",
         LEGACY / "goal_orientation_and_performance_adaptation" / "output" / "gemini_2.5_flash",
         LEGACY / "goal_orientation_and_performance_adaptation" / "ground_truth.json", goal_targets),
        ("gratitude_loneliness_2024", "Gratitude & Loneliness (Hittner 2024)",
         LEGACY / "meta_gratitude_loneliness" / "output", LEGACY / "meta_gratitude_loneliness" / "ground_truth.json",
         ["r", "N", "female", "M_age", "SD_age", "usa_vs_other"]),
        ("intelligence_creativity_2021", "Intelligence & Creative Achievement (Karwowski 2021)",
         LEGACY / "meta_intelligence" / "output", LEGACY / "meta_intelligence" / "ground_truth.json",
         ["SAMPLE SIZE", "ES", "Mage", "IQ modality", "IQ Aspect", "Creativity Measures", "Domain classified"]),
    ]
    for ma, title, root, gt, targets in s4:
        fname = f"{ma}.html"
        m = build_v1(ma=ma, results_root=root, gt_path=gt, targets=targets, papers=None,
                     csv_rows=_cells(ma), out=out / fname)
        add(title, "Study 4", "v1", "gemini-2.5-flash", "0", fname, m)

    # --- v2: Study 5
    for key, ma, title, pipeline in (
        ("vu", "vu2024", "Willful ignorance (Vu 2023)", "v2"),
        ("ng", "ng2023", "Youth depression psychotherapy (Ng 2023)", "v2"),
        ("bennett", "bennett2023", "Male suicide risk & recovery (Bennett 2023)", "v2"),
        ("buecker", "buecker2023", "Subjective well-being across the life span (Buecker 2023)", "v2"),
        ("bowes", "bowes2023", "Conspiracy beliefs (Bowes 2023)", "v2-singlepass"),
    ):
        fname = f"{ma}.html"
        m = build_v2(key, ma, out / fname)
        add(title, "Study 5", pipeline, "gemini-2.5-flash", "0", fname, m)

    _index(index, out / "index.html")
    for r in index:
        print(f"{r['file']:45s} papers={r['n_papers']:3d} items={r['n_items']:4d} "
              f"P={r['precision']:.4f} R={r['recall']:.4f} F1={r['f1']:.4f}")
    print(f"\n{len(index)} pages + index.html -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
