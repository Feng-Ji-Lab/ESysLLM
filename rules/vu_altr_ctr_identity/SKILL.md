---
name: vu_altr_ctr_identity
description: Derive N_Altr_CI_Ctr from the identity N_Tot_CI_Ctr − N_Self_CI_Ctr rather than searching the paper for an explicit "N prosocial choices in baseline" sentence.
activates_on:
  - text_pass
  - asset_pass
  - derive
applies_to:
  - N_Altr_CI_Ctr
---

PREFERRED extraction strategy for `N_Altr_CI_Ctr`:

Identity: `N_Altr_CI_Ctr = N_Tot_CI_Ctr - N_Self_CI_Ctr`

Every participant in the conflict state of the Ctr condition either chose
selfishly or altruistically — there is no third option, no missing data. The
identity therefore holds EXACTLY for every paper in this meta-analysis.

EXTRACTION ORDER:
1. First locate `N_Tot_CI_Ctr` — total participants in the conflict state of
   the Ctr condition. This is usually a clean "n = …" in tables, often in the
   row/column header. Examples:
     - Dana 2007 Baseline n = 19
     - Bartling 2014 Baseline n = 27
     - Lind 2019 Baselline [sic] n = 45
2. Then locate `N_Self_CI_Ctr` — count of selfish choices. Often reported as a
   proportion ("75% chose selfishly") which must be converted to an integer
   using `round(prop × N_Tot_CI_Ctr)`.
3. Derive `N_Altr_CI_Ctr = N_Tot_CI_Ctr − N_Self_CI_Ctr`. Cite the table /
   evidence rows used to obtain N_Tot and N_Self in `evidence_source` and
   record the derivation in `inference_reason` (e.g.,
   "Derived: 14 = 19 − 5; N_Tot from Table 1 row 'Baseline n', N_Self from
   Results §3.1 '5 of 19 chose selfishly'").

WHY NOT FREE-TEXT SEARCH:
Many papers don't directly report "N prosocial choices in baseline" — they
report the prosocial rate as a percentage in the Results prose ("60% chose
the prosocial option in baseline") and leave the count for the reader to
compute. A naive prompt would ask the LLM to find an explicit count which is
why their accuracy is 12.9%. The identity-based derivation is exact and
reproducible.

CROSS-CHECK:
If the paper does report an explicit count of prosocial choices, verify that
it equals N_Tot_CI_Ctr − N_Self_CI_Ctr (within 1 for rounding). If they
disagree by more than 1, flag in `warning`.
