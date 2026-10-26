---
name: infer_college_sample_100
description: A college sample implies 100% college-or-higher education
activates_on: [aggregator, derive]
executor: infer_college_sample_100
applies_to: [Percentage of college or higher of participants]
---

If a sample's source is a college/university (e.g. "college students"), its
percentage of participants with college-or-higher education is 100% — those
participants are, by definition, enrolled in college. Apply only when the field
is not already reported for that sample.
