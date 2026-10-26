---
name: vu_cell_terminology
description: Translate per-paper Tmt/Ctr names into the canonical HI vs FI / conflict-state axis used by all N_*_CI_* fields.
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

Cell-extraction terminology (CRITICAL — wrong axis = wrong cell = wrong number).

VARIABLE DECOMPOSITION:
- `N_<choice>_CI_<treatment>`: the `_CI_` infix means CONFLICT STATE (the cell
  where the dictator's selfish option harms the recipient — $6/$1 in Dana 2007).
  The OPPOSITE is `_AI_` (aligned state, $5/$5) — NOT extracted in this MA.
- `<choice>` = `Self` (selfish, max-own-payoff, $6/$1, "option A") or `Altr`
  (altruistic/prosocial, $5/$5, "option B") or `Tot` (total).
- `<treatment>` = `Tmt` (Hidden Information / HI / EXPERIMENTAL) or `Ctr`
  (Full Information / FI / CONTROL / BASELINE).

TMT vs CTR ASSIGNMENT (the most common source of mis-extraction):
- `Tmt` is ALWAYS the **Hidden Information** condition (the manipulation of
  interest). NEVER the baseline.
- `Ctr` is ALWAYS the **Full Information** condition (the visible-payoffs
  baseline). NEVER the manipulation.

Common paper-side names you must MAP to Tmt (HI):
  "Hidden information", "Hidden payoff", "Non-transparent", "Hidden – conflict",
  "Hidden – time pressure", "Period 2" (Matthey & Regner 2011),
  "Default NR" / "Default R" / "Active choice" (Grossman 2014's 3 HI variants
  all share one Baseline), "Choice" / "Choice-UR" / "Choice-H" (Conrads 2013's
  3 HI variants), "Reveal bonus" (Grossman 2014 paid-reveal variant),
  "Dictator – Ruler – Hidden" (Cerrone & Engel 2019).

Common paper-side names you must MAP to Ctr (FI baseline):
  "Baseline", "Transparent", "Known information", "Revealed state",
  "Standard dictator", "Standard dictator game", "CIG Only", "Period 1",
  "Control", "Open", "Public payoffs", "Dictator – Ruler" (Cerrone & Engel).

CHOICE TYPES:
- "Selfish choice" = the option that MAXIMIZES the dictator's payoff at the
  recipient's expense. Synonyms: "option A", "$6/$1", "selfish option",
  "self-interested choice", "X option", "self-serving choice".
- "Altruistic" / "prosocial choice" = the option that EQUALIZES or FAVORS the
  recipient. Synonyms: "option B", "$5/$5", "prosocial option", "fair choice",
  "Y option".

SHARED CTR REPLICATION (Grossman 2014, Lind 2019, Conrads 2013, Kappes 2018):
When the same paper reports MULTIPLE Tmt variants all compared against ONE
shared Ctr (e.g., Grossman 2014 has Default-NR / Active / Default-R all vs
Baseline), each (Tmt × Ctr) pair is a separate cell. The Ctr-side N values
are REPLICATED across all cells sharing the same Ctr_name — that matches
the canonical per-cell encoding. Extract the Ctr-side value ONCE and replicate.

CELL KEYS (sample_label) — write as "<Tmt_name> vs <Ctr_name>", e.g.:
  "Hidden information vs Baseline"
  "Default NR vs Baseline"
  "Default R vs Baseline"
  "Active choice vs Baseline"
  "Hidden info 1 vs Known information 1"
  "Choice vs Transparency"
  "Period 2 vs Period 1" (within-subject — see vu_within_subject)

ALWAYS extract integers — never proportions. If the paper reports "50% of
n=40 chose selfishly", emit N_Self = 20. Quote the cell value verbatim in the
evidence (e.g., "Table 2, row 'Hidden information', column 'N selfish'") with
the integer reproduced.
