# Bennett 2023 — study-level extraction benchmark (pilot)

Bennett, S., Robb, K. A., Zortea, T. C., Dickson, A., Richardson, C., & O'Connor, R. C. (2023).
*Male suicide risk and recovery factors: A systematic review and qualitative meta-synthesis of
two decades of research.* Psychological Bulletin, 149(7–8), 371–417. https://doi.org/10.1037/bul0000397

Source review PDF: `Jansen2025/Bennett2023_77/2024-05957-001.pdf`

## What this benchmark is

Bennett is a **qualitative meta-synthesis**, not a quantitative meta-analysis — it has no
means/SDs/Ns/effect sizes. The unit of extraction is the **primary study** included in the
review (~69–78 of them). For each primary study, the task is to extract **4 categorical
variables**, matching exactly what Jansen 2025 benchmarked:

| Variable | Meaning | Gold cleanliness | Jansen 8-model accuracy |
|---|---|---|---|
| `Country` | country the study was conducted in | clean (67/69 single-valued) | 83.3 – 94.4 % |
| `Type` | primary vs secondary data | clean but **degenerate** (~all "primary"; κ≈0) | 65.2 – 82.2 % |
| `Population` | suicide outcome group | **messy** (24+ strings, compound labels, typos) | 34.7 – 64.6 % |
| `Area` | risk vs recovery focus | **multi-label** (49/69 are BOTH) | 49.5 – 71.2 % |

This is a *study-level categorical-coding* benchmark, directly comparable to Jansen's published
per-model numbers — unlike the Supplement G 9-column table, which Jansen never scored and whose
only in-paper source is the supplement itself (source leakage).

## Provenance of the gold

`gold_studylevel.csv` is pivoted from Jansen's own scoring file
`Jansen2025/osfstorage-archive/Archive/analysis/d_long.xlsx` (sheet `Sheet1`, `meta=='Bennett2023'`),
which scores at **(study × variable × model)** granularity: column `code` = gold answer,
`llm_answer` = model answer, `llm_code_num` = correctness.

**Harness validation:** aggregating `d_long` by (model × variable) reproduces Jansen's published
per-model accuracy ranges *exactly* for Country/Type/Area and within rounding for Population
(see `docs/reports/2026-06-18-bennett2023-benchmark-feasibility.md`). This confirms the gold +
scoring path before any of our own extraction is run.

## Comparison-unit caveats (read before scoring)

- **Area is multi-label.** 49/69 studies contribute both "risk" and "recovery" quotes, so a single
  per-study Area is ill-defined. Jansen scored Area at the quote/instance level (n≈118/model, not 69).
  Our scorer should treat the gold as a *set* and score set-overlap, not exact string match.
- **Population needs normalization.** Gold strings are inconsistent (`attempted suicide (men)` vs
  `attempted suicide (male)`, `mixture` vs `mixed`, the typo `non-attemtped`). A normalization map
  is required or accuracy is artificially depressed.
- **Type is near-constant** ("primary"); report accuracy *and* kappa, since accuracy alone is
  misleading on a degenerate class.
- 69 studies are scored in `d_long`; Supplement G lists 78 and `human_coding_final` has 75. The
  delta is studies Jansen dropped from scoring; we follow `d_long` (the scored set).

## The blocker: source PDFs

Our extraction pipeline reads each **included primary-study PDF** (cf. `data/runs/jansen_ng2023/<Study>/`).
Those ~69 primary papers are **not** in the dataset — only the Bennett review is. The review body
contains no per-study metadata table (it defers to Supplement G), so the primaries must be sourced
to run a real extraction. `study_references.csv` carries the citation + DOI for 53/69; the 10-study
pilot in `pilot_studies.csv` all have clean DOIs.

## Files

| File | Contents |
|---|---|
| `gold_studylevel.csv` | 69 studies × {Country, Population, Type, Area}, pivoted from `d_long` |
| `study_references.csv` | study → DOI + citation, parsed from the Bennett reference list (53/69 matched) |
| `pilot_studies.csv` | the 10-study smoke subset (coverage-greedy: 10 countries, 10 populations, all Types, both Area patterns) — all with DOIs |

## Next steps (pilot, gated on PDFs)

1. Source the 10 pilot PDFs from the DOIs in `pilot_studies.csv` → `data/runs/jansen_bennett2023/<Study>/`.
2. Add a `goldlib_bennett.py` + validator for the 4 categorical vars (with Population normalization
   + multi-label Area scoring).
3. Run our extraction agent on the 10, score against `gold_studylevel.csv`, compare to Jansen's
   per-model baseline.
4. If the harness holds, scale to the full ~69.
