---
name: info_cost_clamp_zero
description: info_cost is a monetary fee — it must be non-negative. Clamp any negative candidate value to 0.0 and explain in reasoning.
activates_on:
  - aggregator
  - derive
applies_to:
  - info_cost
---

`info_cost` is by definition a monetary cost paid by participants to acquire
information. **It cannot be negative.** A negative value is always a model
error (typically caused by misreading a "reveal bonus" or "payment for
participation" as a negative cost).

CLAMPING RULE:
- If a candidate or final value is negative, set it to `0.0` and record
  in `reasoning` that the original value was clamped (e.g.,
  "candidate value -0.1 clamped to 0.0; the paper describes a reveal
  bonus that PAYS participants, which is not an information cost").
- This applies AFTER all other selection heuristics — if the only
  candidate is negative, clamp it.

VALID RANGE:
- `0.0` ≤ info_cost ≤ ~10 (in 2015 USD; values above $10 should also
  be flagged as suspect — most paradigms charge < $1 if anything).
- The most common correct value is `0.0` (free reveal).
