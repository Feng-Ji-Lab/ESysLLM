---
name: estimate_yeart1_from_pubyear
description: Estimate the baseline year (yearT1) from publication year when the paper does not state it
activates_on: [derive]
executor: estimate_yeart1_from_pubyear
applies_to: [yearT1]
---

When a study does not report the calendar year of its first assessment (yearT1
resolves to None), estimate it with the Buecker (2023) meta-analysts' own coding rule
for `infoYearT1 = 3 (Estimated)`:

    yearT1 = publication_year − (3 years + interval between Time 1 and the last
             assessment included in the study)

i.e. `yearT1 = publication_year − 3 − span`. The publication year is supplied per
paper via `context["publication_year"]`, sourced from the study's entry in the
Buecker reference list (`schemas/buecker2023/publication_years.json`). The span
(T1→last wave) is estimated from the extracted payload as (max wave number − 1) × lag,
falling back to 2 years when waves/lag are unavailable. Applies only when yearT1 is
missing; a stated/extracted year is left untouched.
