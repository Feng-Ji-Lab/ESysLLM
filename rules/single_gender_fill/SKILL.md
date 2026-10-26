---
name: single_gender_fill
description: Fill the gendered slot for a single-gender sample reported only as a total.
executor: single_gender_fill
activates_on: []
applies_to:
  - Sample
  - Mean BMI of participants
  - Correlation between body appreciation and BMI
---
When the census marks a sample as all_female or all_male and a gender-specific field
holds only a total, set the present gender's slot equal to the total and the absent
gender's slot to null. Never overwrite an existing female/male breakdown.
