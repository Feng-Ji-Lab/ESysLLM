# ESysLLM — LLM-based data extraction and coding for evidence synthesis

Companion code, outputs and reference data for

> Zhang, Y.\*, Luo, N.\*, Kim, H., Li, L., Gao, L., Han, J., Chen, S., Zhang, X., He, J., & Ji, F.
> *Large Language Models (LLMs) for Evidence Synthesis: An Exploratory Evaluation and A New
> Approach for Automated Data Extraction and Validation.* Preprint: https://doi.org/10.31234/osf.io/udysp_v2
> (\* equal contribution)

The paper proposes the **Divide, Conquer, then Recheck (DCR)** workflow: split an article
into sections, extract each section (and each table/figure) in its own LLM call with
JSON-constrained output and cited evidence, then reconcile the candidates per field.
Two implementations are in this repository:

| | Where | Used for | Prompts |
|---|---|---|---|
| **v2 — `mag`** (main code) | `src/mag`, `schemas/`, `rules/` | Study 5: five meta-analyses from the Jansen et al. (2025) benchmark | prose slots in `schemas/<ma>/prompts.yaml` + rule packs; `[block_id]`-cited evidence; sample census + per-field aggregation — see [docs/methods_v2_prompts.md](docs/methods_v2_prompts.md) |
| **v1** (archived, unchanged) | `legacy/v1/` | Studies 2–4, Supplemental Material C–D | JSON system/user/aggregation templates + table-reading rules |

Study 5's conspiracy-belief dataset (Bowes 2023) was extracted with a separate
single-pass script, `scripts/extract_bowes.py`, not with the section-level pipeline.
No extraction was rerun for this release: outputs are the ones behind the manuscript.

## What is here

```
src/mag/                 v2 pipeline (preprocessing → stage-1 section passes → census → per-field aggregation → executors)
schemas/<ma>/            fields.json + prompts.yaml per meta-analysis (default, bas-bmi, vu2024, ng2023, bennett2023, bowes2023, buecker2023)
rules/<pack>/SKILL.md    rule packs injected into prompts; some carry executors (src/mag/skills)
scripts/                 run_jansen_bench.py / run_extract.py (extraction), extract_bowes.py, score_*.py (ours and Jansen re-scored),
                         export_scored_cells.py, build_summary.py, build_all_dashboards.py, fir/ (Marker SLURM jobs)
eval/_dashboard/         scoring classifiers + dashboard builder; eval/<ma>/ gold CSVs; eval/_jansen/ third-party files (PROVENANCE.md)
results/<ma>/raw/        as-run outputs: Vu 15, Ng 31, Bennett 69 (3 batches), Buecker 101, Bowes 100 papers
results/<ma>/scored_cells.csv   one row per scored paper × field for all nine meta-analyses (same columns everywhere)
results/paper_numbers.yaml, results/summary.csv   every number in the manuscript → selection → recomputed value
dashboard/               index.html + 17 pages (one per meta-analysis; He2020 per model × temperature)
legacy/v1/               the R1 release plus its ground truth, table rules and three small repairs (see below)
docs/                    methods_v2_prompts.md, reproduction.md, known_discrepancies.md
```

Marker full-text conversions of the primary articles are **not** included for Study 5
(copyright); `legacy/v1` keeps what the R1 release already contained.

## Results at a glance

Metric = the paper's coverage rule: a paper × field item is correct when every reference
value appears in the extraction (extra values allowed); micro-averaged F1. All values
are recomputed from `results/*/scored_cells.csv` by `scripts/build_summary.py`.

| Study | Dataset | Pipeline / model | Papers | F1 |
|---|---|---|--:|--:|
| 3 | He 2020, Body Appreciation × BMI | v1 / Gemini 2.5 Flash | 56 | 0.988 |
| 3 | 〃 | v1 / GPT-5-mini | 56 | 0.968 |
| 3 | 〃 | v1 / Claude Haiku 4.5 | 56 | 0.946 |
| 4 | Goal orientation (Stasielowicz 2019) | v1 / Gemini 2.5 Flash | 13 | 0.976 |
| 4 | Gratitude–loneliness (Hittner 2024) | v1 / Gemini 2.5 Flash | 17 | 0.979 |
| 4 | Intelligence–creativity (Karwowski 2021) | v1 / Gemini 2.5 Flash | 18 | 0.963 |
| 5 | Subjective well-being (Buecker 2023) | v2 / Gemini 2.5 Flash | 99 | 0.916 (Jansen best model 0.873) |
| 5 | Male suicide (Bennett 2023) | v2 / Gemini 2.5 Flash | 69 | 0.900 (68-paper head-to-head 0.899; Jansen best 0.874) |
| 5 | Youth depression psychotherapy (Ng 2023) | v2 / Gemini 2.5 Flash | 31 | 0.848 (30-paper head-to-head 0.852; Jansen best 0.738) |
| 5 | Willful ignorance (Vu 2023) | v2 / Gemini 2.5 Flash | 15 | 0.831 (Jansen best 0.615) |
| 5 | Conspiracy beliefs (Bowes 2023) | single-pass / Gemini 2.5 Flash | 100 | 0.831 (Jansen best 0.720) |

"Jansen best" is the best of Jansen et al.'s eight models, re-scored with the same
classifier on the same papers and fields (`scripts/score_*_jansen*.py`). Per-field
numbers, precision/recall and the strict (exact-match) standard are in
`results/summary.csv` and on each dashboard page.

## Reproduce

```bash
pip install -e . && pip install pandas openpyxl
PYTHONPATH=.:src python scripts/export_scored_cells.py     # results/<ma>/scored_cells.csv
PYTHONPATH=.:src python scripts/build_summary.py           # checks every manuscript number; exit 0
PYTHONPATH=.:src python scripts/build_all_dashboards.py    # dashboard/
```

Step-by-step commands per study, and how to rerun extraction on new PDFs, are in
[docs/reproduction.md](docs/reproduction.md).

## Read before citing the numbers

[docs/known_discrepancies.md](docs/known_discrepancies.md) lists the places where the
manuscript text and this repository disagree (temperature claim, Table 3 Ng sample size,
"macro" vs micro averaging, prompt-structure statements, Bowes method, Buecker values
filled by codebook executors, 56 of 60 He2020 papers). The numbers reproduce; the
wording around some of them does not yet.

Known limitations of the code as released:

- `src/mag` is the 2026-07-09 state. The Vu/Ng/Bennett/Bowes runs used earlier,
  uncommitted versions of a few files; the prompts, schemas and rule packs are unchanged
  since every run.
- The batch driver injects **every** rule pack under `rules/` into every prompt,
  whichever meta-analysis is being extracted.
- `fields.json` keys `case_rules`, `value_labels`, `skill_hints` are not read by the code.
- v2 has a Gemini provider only (Vertex AI or API key); the three-model comparison of
  Study 3 was run with v1.
- Studies 1–2 (chatbot interfaces, GPT-4o) and the bar-chart figures cannot be
  re-derived from this repository; their source material was not archived here.
- `legacy/v1` repairs: a comment in `validation/build_dashboard.py` that had lost its
  `#` and did not parse; absolute workstation paths in two ground-truth helper scripts.
  Scoring logic is untouched and reproduces Studies 3–4 and Appendix D exactly.

## Data and licences

Code is MIT (see `LICENSE`). `results/` and `eval/<ma>/` are ours. `eval/_jansen/`
holds six files from Jansen et al. (2025) and from the Vu and Ng meta-analysis authors,
redistributed only because the scorers open them — see `eval/_jansen/PROVENANCE.md` and
cite the original sources. Ground truth for He2020 and the Study-4 datasets is in
`legacy/v1/*/ground_truth.json` with its source spreadsheets.

## Citation

See `CITATION.cff`.
