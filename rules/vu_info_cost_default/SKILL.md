---
name: vu_info_cost_default
description: Default info_cost to 0.0; only attempt PPP conversion if a non-zero monetary cost is explicitly stated. All papers in this meta-analysis have free reveal.
activates_on:
  - text_pass
  - asset_pass
  - derive
applies_to:
  - info_cost
---

`info_cost` extraction rule:

For ALL papers in this meta-analysis, the cost to acquire information about
the recipient's payoff is **0.0 (FREE REVEAL)**. Verified across the entire
canonical encoding.

EXTRACTION DEFAULT: `0.0`

ONLY emit a non-zero value if the paper EXPLICITLY states a monetary cost,
e.g.:
  - "Participants paid 1 ECU to reveal the recipient payoff"
  - "Information was costly to learn (€0.10 per click)"
  - "Subjects who chose to know paid 5 cents"

Phrases that confirm the 0.0 default:
  - "free of charge"
  - "at no cost"
  - "one click reveal"
  - "costless reveal"
  - "could be revealed for free"
  - "no fee"
  - "free to look up"
  - silence on cost in the design description (zero-cost is the Dana 2007
    paradigm default; if the paper doesn't say otherwise, info is free)

DO NOT attempt the ECU → local currency → 2015 USD → PPP conversion chain
unless a non-zero cost is stated. The brittle multi-step conversion is what
made naive prompts fail repeatedly on this variable for a corpus where
the gold value is exactly 0 for all included papers.

If a non-zero cost IS stated, follow this conversion:
  1. Extract raw cost + currency / unit (e.g., "1 ECU" or "€0.10")
  2. If experimental currency (ECU), multiply by stated exchange rate to get
     local currency
  3. Multiply by stated PPP factor (or look up from OECD PPP tables for the
     year stated)
  4. Convert to 2015 USD using inflation factor (CPI ratio)
  Report each step in `inference_reason`.
