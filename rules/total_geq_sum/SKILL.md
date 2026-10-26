---
name: total_geq_sum
description: A sample's total N must be at least the sum of its female and male Ns
activates_on: [derive]
validator: total_geq_sum
applies_to: [Sample]
---

For a gender-specific count field, the total must be greater than or equal to the
sum of the female and male counts. A smaller total signals a misread or a
mismatched gender breakdown and is flagged for review.
