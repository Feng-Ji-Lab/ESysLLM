---
name: gender-mapping
description: Activates on every pass to normalise gender labels and infer single-gender studies
activates_on:
  - text_pass
  - asset_pass
---

Gender mapping rules
====================

- Map the paper's gender labels to exactly one of {`male`, `female`, `other`,
  `total`}. Treat "women" / "girls" / "female participants" as `female`;
  "men" / "boys" / "male participants" as `male`; "non-binary" / "prefer not
  to say" as `other`; whole-sample counts as `total`.
- If a paper explicitly reports a single-gender sample (e.g., "all-female
  nursing students, N=326"), populate BOTH `female` AND `total` with the same
  value, noting in `inference_reason` that the study is single-gender.
- Never invent a gender split when the source reports only a total. Return
  `null` for the missing subgroup.
