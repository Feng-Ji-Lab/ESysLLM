---
name: vu_country_mturk
description: Map US-based online panels (MTurk, Prolific, CloudResearch) to "mturk/prolifics" rather than "united states"; apply country synonyms.
activates_on:
  - text_pass
  - asset_pass
applies_to:
  - country
---

`country` enum is constrained to 5 lowercase values:
  `germany`, `mturk/prolifics`, `norway`, `switzerland`, `united states`

DECISION TREE:
1. Was the study run on Amazon Mechanical Turk, Prolific (Academic),
   CloudResearch, or any US-based online panel? → `mturk/prolifics`
2. Lab/university in the United States (other than MTurk-style online)? →
   `united states`
3. Lab in Germany or Deutschland? → `germany`
4. Lab in Switzerland / Schweiz / Suisse / Svizzera? → `switzerland`
5. Lab in Norway / Norge? → `norway`

ONLINE-PANEL KEYWORDS that trigger `mturk/prolifics`:
  "Amazon Mechanical Turk", "MTurk", "Mechanical Turk", "Prolific",
  "Prolific Academic", "CloudResearch", "MTurk Prime"

SYNONYMS:
  `united states`: USA, U.S., U.S.A., United States of America, US, America,
                   American
  `germany`:       Deutschland
  `switzerland`:   Schweiz, Suisse, Svizzera

EXAMPLES from included papers:
  - Dana 2007 (Carnegie Mellon lab) → united states
  - Bartling 2014 (Zurich) → switzerland
  - Cerrone & Engel 2019 (Bonn) → germany
  - Exley & Kessler 2020 (Harvard, but MTurk recruitment) → mturk/prolifics
  - Kappes 2018 (Crockett Oxford lab, but MTurk recruitment) → mturk/prolifics
  - Lind 2019 (Oslo) → norway

CAUTION: a US university lab that runs MTurk recruitment counts as
`mturk/prolifics`, NOT `united states` — the determining factor is the
recruitment platform, not the lab location.

Countries NOT in the enum (papers conducted in other countries are excluded
from this analysis):
  - Netherlands — emit "None" if you see this
  - France — emit "None" if you see this
