"""Tests for the compare_extraction report builder."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "compare_extraction", Path("scripts/compare_extraction.py")
)
compare_extraction = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare_extraction)

TARGET = {"Author": "Tylka", "Sample": {"Study 1 - college sample": [675, 367, 308]}}
EXTRACTED = {"Author": "Tylka", "Sample": {"Study 1 - 675 participants": [675, 367, 308]}}


def test_build_report_has_table_and_totals():
    md = compare_extraction.build_report(EXTRACTED, TARGET, tol=0.05)
    assert "| Field |" in md  # per-field table header
    assert "Author" in md and "Sample" in md
    assert "precision" in md.lower()
    assert "1.000" in md  # perfect precision on this toy input


def test_build_report_flags_a_mismatch():
    extracted = {
        "Author": "Someone Else",
        "Sample": {"Study 1 - 675 participants": [675, 367, 308]},
    }
    md = compare_extraction.build_report(extracted, TARGET, tol=0.05)
    # Author incorrect → overall precision < 1
    assert "Author" in md
