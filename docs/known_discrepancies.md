# Where the manuscript text and this repository disagree

Compiled while assembling the release (October 2026) by re-deriving every reported
number from the archived outputs. Numbers themselves reproduce (see
`results/summary.csv`); the items below are places where the *text* around them, or
a sample size, does not match what the code did. They are listed so readers can
weigh the results correctly and so the authors can align the manuscript. Nothing in
the repository was changed to hide them.

| # | Manuscript | Repository |
|---|---|---|
| 1 | §3.3 and Appendix D: temperature 0 gave the strongest, most stable extraction for all three models. | On the five-paper subset, only Gemini 2.5 Flash peaks at T = 0 (F1 1.000 vs 0.991). GPT-5-mini peaks at T = 0.2 (1.000 vs 0.982 at T = 0). Claude Haiku 4.5 is lowest at T = 0 (0.936 vs 0.946 at 0.2 and 0.4). The Appendix D figure shows this; the sentence does not. Source: `results/he2020/scored_cells.csv`, `study = "Appendix D"`. |
| 2 | Table 3, Ng 2023 row: *n* = 30, DCR F1 = 0.848. | 0.848 is the F1 over the 31 papers we scored. The head-to-head set with Jansen's codings has 30 papers (Jansen's `TADS2003` vs our `TADS2004` label); on those 30 our F1 is 0.852. Either *n* = 31 with 0.848, or *n* = 30 with 0.852. |
| 3 | §3.5 and Table 3 note: "macro-averaged F1". | All Study 5 scorers pool CED/IED/MD over paper × field items before computing F1 (micro-averaging). The earlier Jansen-matching macro-F1 figures (Vu 0.738, Ng 0.817) are not the ones in Table 3. |
| 4 | §3.5 cost paragraph: Ng dataset "30 articles", ≈ 0.28 M input / 0.04 M output tokens per article; Vu ≈ 0.45 M / 0.07 M. | 31 Ng articles were run (median 14 pages over 31; 15 over 30). Token totals recorded in the run logs bracket the stated figures (Ng: 0.268–0.289 M input, 0.036–0.041 M output per article depending on which attempt is counted; Vu: 0.42–0.53 M / 0.07–0.09 M). The exact calculation behind the printed numbers was not archived; treat them as approximate. |
| 5 | §2.3 defines "partial match" (reference value present, extra values extracted) as incorrectly extracted data (IED). | Every scorer that produced the reported numbers counts a partial match as correct — the coverage rule stated in §3.5 ("a reference value counts as recovered when it appears within the pipeline's extraction"). `scored_cells.csv` carries both standards (`correct_coverage`, `correct_strict`). |
| 6 | §2.2.5: "The structure of the prompts was the same as in Study 4"; §2.2: prompt template and aggregation procedure held constant across the nine meta-analyses; §2.1: all prompts are JSON objects; Appendix C shows JSON prompts. | Studies 2–4 used the v1 JSON-prompt pipeline (`legacy/v1`). Study 5 used the v2 pipeline, whose prompts are prose slots in `schemas/<ma>/prompts.yaml` plus rule packs, with a sample-census stage and per-field aggregation; nearly every slot was rewritten per meta-analysis. See `docs/methods_v2_prompts.md`. |
| 7 | §2.1 / §3.5: multi-pass section reading and evidence-based rechecking explain the Bowes gains. | Bowes was extracted by `scripts/extract_bowes.py`: one model call per paper over the whole Marker text, table grids and up to 12 table/figure images; no section passes, no aggregation stage. The Bowes advantage comes from multimodal table reading in a single pass. |
| 8 | §3.5: Buecker `yearT1` F1 0.900 cited as near-perfect extraction. | 30 of 101 `yearT1` values and 33 of 101 `ethnicity` values were produced by code executors (`rules/estimate_yeart1_from_pubyear`, `rules/infer_ethnicity_from_country`) that mirror the meta-analysts' codebook rules, not read from the article. They are tagged `derived:<skill>` in `results/buecker2023/scored_cells.csv`. |
| 9 | §2.2.1: He2020 comprises 60 primary articles. | Study 3 and Appendix D scores are over the 56 articles that have pipeline outputs (`1Howell2018`, `1Luu2014`, `1Swami2010Associations between trait emotional`, `1Thall2014121` have none for any model). |
| 10 | Studies 1–2 (chatbot interfaces; GPT-4o chatbot vs DCR). | No rater sheets, GPT-4o outputs or figure-generating code for these studies exist in this repository; those numbers cannot be re-derived here. |

## Code state caveats (not text issues)

- The `src/mag` tree is the state of 9 July 2026. The Vu, Ng, Bennett and Bowes runs
  (30 May – 30 June) used earlier, uncommitted states of a few files
  (`orchestrator.py`, `section_builder.py`, `candidate_format.py`, `providers/gemini.py`,
  `settings.py`, `derive/registry.py`, `manifest_normalizer.py`). The prompt, schema
  and rule files are unchanged since every run. Buecker (7–9 July) matches this tree.
- `scripts/run_jansen_bench.py` loads every pack under `rules/` and stage 1 injects all
  of them into every prompt, so each meta-analysis was extracted with the other
  meta-analyses' rules present (17–19 packs per call). The `hien_arm_taxonomy` pack is
  kept for that reason although Hien2024 is not in the paper.
- `fields.json` keys `case_rules`, `value_labels` and `skill_hints` are not read by
  any code path; only `name`, `type`, `items_type`, `allowed_values`, `definition`
  reach the model, and `skills` drives the executor stage.
- `legacy/v1/validation/build_dashboard.py` line 30 did not parse in the released
  file (a comment had lost its `#`); it is restored as a comment. Two legacy helper
  scripts had absolute paths from the original workstation and now resolve paths from
  their own location. No scoring logic in `legacy/v1` was changed.
