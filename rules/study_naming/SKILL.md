---
name: study_naming
description: How to name studies and samples when extracting and aggregating
activates_on: [text_pass, asset_pass, aggregator]
---

A paper may report multiple studies, and a study may contain multiple distinct
samples (e.g. a college sample and a community sample, or a test-retest
subsample). Name each distinct sample with the key format
`Study <n> - <descriptive label>`, using the label **exactly as written in the
paper** (e.g. "college students", "MTurk community participants",
"test-retest subsample"). Do not normalize, abbreviate, or invent labels.

If a section names a study only loosely (e.g. "the second study"), use the
clearest available label; a later aggregation step reconciles names across
sections. Never merge two clearly distinct samples into one key.
