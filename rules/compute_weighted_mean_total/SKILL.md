---
name: compute_weighted_mean_total
description: Compute a gender-specific field's total as the size-weighted mean of female/male
activates_on: [aggregator, derive]
executor: compute_weighted_mean_total
applies_to: [Mean BMI of participants]
precision: 4
---

When a gender-specific field reports female and male means but no overall total,
the total for the whole sample is the sample-size-weighted average:
`(mean_female * n_female + mean_male * n_male) / (n_female + n_male)`, where the
counts come from the Sample field. Keep at least 4 decimal places; do not round
to the nearest tenth.
