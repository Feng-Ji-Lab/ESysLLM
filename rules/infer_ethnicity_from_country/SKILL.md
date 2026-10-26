---
name: infer_ethnicity_from_country
description: Infer predominant ethnicity from country when the paper does not report it
activates_on: [derive]
executor: infer_ethnicity_from_country
applies_to: [ethnicity]
---

When a study does not report the racial/ethnic composition of its sample, infer the
predominant ethnicity from the sample's country, following the meta-analysts' own
coding convention (Buecker 2023): European / European-heritage countries (Germany,
UK, Sweden, Netherlands, Poland, Australia, …) → "predominantly white/european";
East-Asian countries (China, Japan, Korea, …) → "predominantly asian". USA / Canada
are deliberately excluded (genuinely multi-ethnic — rely on reported data there).
Applies only when ethnicity is missing or "not specified"; a reported composition is
left untouched.
