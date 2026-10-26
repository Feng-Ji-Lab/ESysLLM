"""Compare an extracted target-shaped dict against a fixture target-shaped dict.

Sample keys differ between the two (paper-faithful vs normalized), so samples are
aligned by (study_index, Sample total) rather than by key string.
"""

from __future__ import annotations

import re
from typing import Any

_STUDY_RE = re.compile(r"\s*study\s+(\d+)", re.IGNORECASE)


def _study_index(key: str) -> int | None:
    m = _STUDY_RE.match(key)
    return int(m.group(1)) if m else None


def _is_absent(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0 or all(x is None for x in value)
    return False


def _is_num(x: Any) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def _scalar_match(t: Any, e: Any, tol: float) -> bool:
    if t is None and e is None:
        return True
    if t is None or e is None:
        return False
    if _is_num(t) and _is_num(e):
        return abs(t - e) <= tol
    return str(t).strip().lower() == str(e).strip().lower()


def _cell_match(t_vals: object, e_vals: list, tol: float) -> bool:
    # A target cell may offer several acceptable answers: {"any_of": [[...], [...]]}.
    if isinstance(t_vals, dict) and "any_of" in t_vals:
        return any(_cell_match(alt, e_vals, tol) for alt in t_vals["any_of"])
    if not isinstance(t_vals, list) or not isinstance(e_vals, list):
        return False
    if len(t_vals) != len(e_vals):
        return False
    return all(_scalar_match(t, e, tol) for t, e in zip(t_vals, e_vals, strict=False))


def _totals_index(d: dict) -> dict[tuple[int | None, Any], str]:
    """(study_index, Sample total) -> sample key, from the Sample field.

    A (study_index, total) seen on more than one sample is AMBIGUOUS and is
    dropped: aligning by total alone can't disambiguate, so those samples are
    left unmatched (scored as missing) rather than silently mis-aligned.
    """
    seen: dict[tuple[int | None, Any], str] = {}
    ambiguous: set[tuple[int | None, Any]] = set()
    sample = d.get("Sample")
    if isinstance(sample, dict):
        for key, vals in sample.items():
            total = vals[0] if isinstance(vals, list) and vals else None
            k = (_study_index(key), total)
            if k in seen:
                ambiguous.add(k)
            else:
                seen[k] = key
    return {k: v for k, v in seen.items() if k not in ambiguous}


def align_samples(extracted: dict, target: dict) -> dict[str, str | None]:
    """Map each target sample key → the extracted sample key with the same
    (study_index, Sample total), or None if unmatched."""
    ext_index = _totals_index(extracted)
    mapping: dict[str, str | None] = {}
    sample = target.get("Sample")
    if isinstance(sample, dict):
        for key, vals in sample.items():
            total = vals[0] if isinstance(vals, list) and vals else None
            mapping[key] = ext_index.get((_study_index(key), total))
    return mapping


def score(
    extracted: dict,
    target: dict,
    *,
    tol: float = 0.05,
    fields: list[str] | None = None,
    field_tol: dict[str, float] | None = None,
) -> dict:
    """Per-field correct/incorrect/missing + overall precision/recall/F1.

    Metrics are computed over the TARGET's present values only: every target cell
    that isn't absent is scored (correct / incorrect / missing); extracted values
    with no corresponding target are not counted. `tol` is an absolute, uniform
    numeric tolerance applied to every numeric field. `field_tol` is an optional
    per-field override: ``{"field name": tolerance}`` — any field listed there uses
    its own tolerance instead of `tol`.
    """
    mapping = align_samples(extracted, target)
    field_names = fields if fields is not None else list(target.keys())
    per_field: dict[str, dict[str, int]] = {}

    for field in field_names:
        t_val = target.get(field)
        e_val = extracted.get(field)
        correct = incorrect = missing = 0
        ftol = (field_tol or {}).get(field, tol)

        if isinstance(t_val, dict):  # sample-scoped
            for t_key, t_cell in t_val.items():
                if _is_absent(t_cell):
                    continue
                e_key = mapping.get(t_key)
                e_cell = e_val.get(e_key) if (isinstance(e_val, dict) and e_key) else None
                if _is_absent(e_cell):
                    missing += 1
                elif _cell_match(t_cell, e_cell, ftol):
                    correct += 1
                else:
                    incorrect += 1
        else:  # paper-scoped scalar
            if not _is_absent(t_val):
                if _is_absent(e_val):
                    missing += 1
                elif _scalar_match(t_val, e_val, ftol):
                    correct += 1
                else:
                    incorrect += 1

        per_field[field] = {"correct": correct, "incorrect": incorrect, "missing": missing}

    c = sum(f["correct"] for f in per_field.values())
    i = sum(f["incorrect"] for f in per_field.values())
    m = sum(f["missing"] for f in per_field.values())
    precision = c / (c + i) if (c + i) else 0.0
    recall = c / (c + m) if (c + m) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "per_field": per_field,
        "totals": {
            "correct": c,
            "incorrect": i,
            "missing": m,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
    }
