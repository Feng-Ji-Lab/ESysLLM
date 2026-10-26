"""Shared types + match classifiers for the evaluation-dashboard gold modules.

Every evaluated (paper, field) is classified into one of four ``klass`` values,
following the measurement standard in the revision paper (CED / IED / MD):

  exact    - extraction fully matches the reference                  (CED)
  contains - reference appears within the extraction, with extras    (IED strict / CED widened)
  wrong    - extraction present but reference not (fully) contained  (IED)
  missing  - reference present, nothing extracted                    (MD)

Two scoring standards are derived from klass:
  strict  CED = exact;            IED = contains + wrong;  MD = missing
  widened CED = exact + contains; IED = wrong;             MD = missing

(``widened`` promotes the paper's "partial match" from incorrect to correct:
the reference value is present in the extracted output even if extra values are.)
"""

from __future__ import annotations

from collections import Counter
from typing import NamedTuple

# klass -> (is_CED, is_IED, is_MD) under each standard
STRICT = {
    "exact": "ced",
    "contains": "ied",
    "wrong": "ied",
    "missing": "md",
}
WIDENED = {
    "exact": "ced",
    "contains": "ced",
    "wrong": "ied",
    "missing": "md",
}


class GoldNotAvailable(Exception):
    """Raised when a (paper, field) has no reference value to compare against.

    The dashboard renders such cells in neutral (gray) — present but unscored.
    """


class CellEval(NamedTuple):
    """Outcome of comparing one extracted (paper, field) against gold."""

    klass: str  # "exact" | "contains" | "wrong" | "missing"
    gold_display: str  # human-readable reference value, shown in the tooltip
    gold_source: str  # which file/source supplied the gold


def classify_set(reference: set, extracted: set) -> str:
    """Classify a set-valued field (e.g. Source, MedCat, IPT)."""
    if not reference:
        return "exact" if not extracted else "wrong"
    if not extracted:
        return "missing"
    if extracted == reference:
        return "exact"
    if reference <= extracted:  # all reference values present, plus extras
        return "contains"
    return "wrong"


def classify_multiset(reference: Counter, extracted: Counter) -> str:
    """Classify a multiset-valued field (e.g. Vu N_* per-cell counts)."""
    if not reference:
        return "exact" if not extracted else "wrong"
    if not extracted:
        return "missing"
    if extracted == reference:
        return "exact"
    if not (reference - extracted):  # reference is a sub-multiset of extracted
        return "contains"
    return "wrong"


def classify_scalar(matched: bool, extracted_present: bool) -> str:
    """Classify a single-valued scalar field (exact match or nothing else)."""
    if not extracted_present:
        return "missing"
    return "exact" if matched else "wrong"
