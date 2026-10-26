---
name: vu_cell_count_localization
description: For cell-level N_*_CI_* fields, the integer to extract is a CELL count from a Results table, NOT a study-level sample size from Methods.
activates_on:
  - text_pass
  - asset_pass
applies_to:
  - N_Self_CI_Tmt
  - N_Self_CI_Ctr
  - N_Altr_CI_Ctr
  - N_Tot_CI_Tmt
  - N_Tot_CI_Ctr
---

WHERE TO LOOK for cell counts (in priority order):

1. **PRIMARY SOURCE — a Results-section TABLE** with cell counts per
   condition. Look for:
   - Tables with row labels like "Hidden information", "Baseline", "Default
     NR", "Choice", "HCT vs HC", etc.
   - Column headers like "N(option A)", "selfish", "altruistic", "fair",
     "selfish A", "fair B", "chose to reveal", "n chose A", "Choices A".
   - When a table reports both selfish and altruistic counts per
     condition, that is the canonical source.

2. **SECONDARY SOURCE — explicit sentences in Results** quoting exact
   integers. Examples:
   - "Of the 19 dictators in baseline, 5 chose the selfish option."
     → N_Self_CI_Ctr = 5, N_Tot_CI_Ctr = 19, N_Altr_CI_Ctr = 14.
   - "In the hidden-payoff condition, 10 of 16 (63%) chose selfish."
     → N_Self_CI_Tmt = 10, N_Tot_CI_Tmt = 16.
   - "Out of 20 dictators in the Dictator-Ruler-Hidden condition, the
     player-X choice was selected 1 time."
     → N_Self_CI_Tmt = 1 (or whichever choice maps to selfish), N_Tot=20.

3. **TERTIARY — derive from percentages WITH N**: when only a percentage
   is reported AND the total N for that cell is known:
   - "75% of dictators chose the selfish option in the conflict state
     (n = 16)" → N_Self_CI_Tmt = round(0.75 × 16) = 12.
   - DO record the derivation in the evidence quote.

NOT A SOURCE — DO NOT extract from:

- **Total-sample N counts** in the Method/Participants section
  ("we recruited 100 participants", "200 students were paid £5"). These
  describe the OVERALL sample, NOT a single cell. Using them for cell-level
  fields is a common and serious error.

- **Percentages without an integer denominator** ("75% of dictators chose
  the selfish option"). If no N is given, set extract_value="None" and
  record this in the evidence.

- **Numbers from prior literature reviews** ("Dana et al. found 5/19
  chose selfish"). If the paper is REPORTING someone else's result,
  do NOT extract — emit "None".

- **Numbers in footnotes or robustness checks** unless they are the
  main reported cell count.

SANITY CHECK before emitting any value:
- N_Self_CI_Tmt + N_Altr_CI_Tmt should equal N_Tot_CI_Tmt (±1 for
  rounding). Same for Ctr side.
- All cell counts must satisfy 0 ≤ N ≤ N_Tot.
- The cell key (Tmt × Ctr label) in your output MUST match the
  (Tmt × Ctr) of the table row you extracted from. If the table is
  for the "Hidden information" treatment but the cell key says
  "Baseline", that's a labeling error — fix the key.

CROSS-CHECK: if the paper reports counts in multiple tables (e.g.,
descriptive table + results table), prefer the table that explicitly
reports cell-level counts over a table that reports a single total.
