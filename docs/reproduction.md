# Reproducing the reported numbers

All commands run from the repository root in a Python 3.11 environment with
`pandas`, `openpyxl`, `pyyaml` and `pydantic` installed (`pip install -e .` plus
`pip install pandas openpyxl`). Nothing below calls an LLM; everything scores the
archived outputs.

## 1. One command for everything

```bash
PYTHONPATH=.:src python scripts/export_scored_cells.py   # results/<ma>/scored_cells.csv
PYTHONPATH=.:src python scripts/build_summary.py         # results/summary.csv, exit 0
PYTHONPATH=.:src python scripts/build_all_dashboards.py  # dashboard/*.html
```

`build_summary.py` recomputes every entry of `results/paper_numbers.yaml` and exits
non-zero if a number without a documented note differs by more than 0.0005 from the
manuscript. Expected: 79 entries, 0 failures, 72 exact matches, 6 informational, 1
documented discrepancy (Table 3 Ng row, *n* = 30 vs 31).

## 2. Study by study, with the original scorers

### Study 3 — He2020, three models at T = 0 (`main.tex` §3.3)

```bash
cd legacy/v1
cp config/settings.example.json config/settings.json   # scorer reads validation_targets from it
python validation/calculate_metrics.py
```
Gemini 2.5 Flash P 0.9776 / R 0.9984; GPT-5-mini 0.9545 / 0.9816; Claude Haiku 4.5 0.9352 / 0.9575.

### Appendix D — temperature sweep (5 papers)

```bash
cd legacy/v1 && python validation/calculate_temp_metrics.py
```
Nine precision/recall pairs; they are the bar labels of the appendix figure.

### Study 4 — Table 2

```bash
cd legacy/v1
python validation/check_13_papers.py      # Goal Orientation: 13 papers, P 0.9521 R 1.0000 F1 0.9755
python validation/temp_calc_metrics.py    # Gratitude-Loneliness 0.9592/1.0000/0.9792; Intelligence 0.9435/0.9832/0.9630
```

The `ground_truth.json` files are the versions used for scoring, i.e. after the
two-reviewer verification described in §2.2. `create_pgo_ground_truth.py` regenerates
the Goal Orientation file identically from `PGO_PA_2019.csv`; `meta_intelligence/convert.py`
produces the pre-verification draft from `OSF-T1_edit.xlsx` (the shipped file differs
in 5 corrected studies and one added study).

### Study 5 — Table 3 and §3.5

Our side (coverage = "Widened" in the script output):

```bash
PYTHONPATH=.:src python -m eval._dashboard.build_dashboard --ma vu --out /tmp/vu.html   # widened F1 0.831
PYTHONPATH=.:src python -m eval._dashboard.build_dashboard --ma ng --out /tmp/ng.html   # widened F1 0.848 (31 papers)
PYTHONPATH=.:src python scripts/score_bennett_ced.py   # Widened OVERALL F1 0.900 (69); 0.899 on the 68-paper head-to-head set
PYTHONPATH=.:src python scripts/score_buecker_ced.py   # WIDENED F1 0.916
PYTHONPATH=.:src python scripts/score_bowes_ced.py     # Widened OVERALL F1 0.831; per-field lines for §3.5
```

Jansen et al. (2025)'s eight models re-scored with the same classifiers on the same
papers and fields (the "Best" and "Mean" columns):

```bash
PYTHONPATH=.:src python scripts/score_buecker_jansen_ced.py   # best 0.873, mean 0.805
PYTHONPATH=.:src python scripts/score_bennett_jansen_ced.py   # best 0.874, mean 0.823
PYTHONPATH=.:src python scripts/score_ng_vu_jansen_ced.py     # Ng best 0.738 mean 0.644; Vu best 0.615 mean 0.527
PYTHONPATH=.:src python scripts/score_bowes_jansen_ced9.py    # best 0.720, mean 0.611; per-field best-of-8
```

These read Jansen's released codings from `eval/_jansen/` (see `PROVENANCE.md` there).

## 3. What cannot be reproduced here

Studies 1 and 2 (chatbot interfaces, GPT-4o chatbot vs DCR) and the bar-chart
figures: the rater sheets, GPT-4o outputs and plotting code were not archived in this
repository. The cost paragraph's token totals are approximate (see
`docs/known_discrepancies.md`).

## 4. Re-running extraction (optional, costs API calls)

1. Convert PDFs with Marker. We ran it on an HPC cluster; `scripts/fir/` holds the
   SLURM job and batch coordinator used. Output per paper: `<id>.json`,
   `<id>_meta.json`, `figures/`, `tables/`, `images/`.
2. Point `MAG_*` settings at your provider (`.env.example`) and run
   `PYTHONPATH=.:src python scripts/run_jansen_bench.py --bench <ma>` for one of the
   bundled schemas, or `scripts/run_extract.py` for a single paper. Outputs land in
   `data/runs/` (gitignored). Bowes uses `scripts/extract_bowes.py` instead.
3. Score with the commands above; `eval/_paths.py::run_dir` falls back to `data/runs/<name>`
   for run names it does not know.
