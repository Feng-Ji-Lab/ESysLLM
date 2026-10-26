"""Target fixtures conform to the 3-field gender convention."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "target_values"
GENDER = {"Sample", "Mean BMI of participants", "Correlation between body appreciation and BMI"}
FILES = [
    "1Tylka2015.json",
    "1Hurst2017.json",
    "1Lemoine2018.json",
    "1Swami2015Associations.json",
    "1Swami2008Factor.json",
]


def _cells(field_val):
    """Yield each cell list, unwrapping any_of alternatives. Skips null (not-reported) cells."""
    for cell in field_val.values():
        if cell is None:
            continue
        if isinstance(cell, dict) and "any_of" in cell:
            yield from cell["any_of"]
        else:
            yield cell


@pytest.mark.parametrize("fname", FILES)
def test_fixture_is_valid_and_conventional(fname):
    data = json.loads((FIX / fname).read_text())
    for field, val in data.items():
        if not isinstance(val, dict):
            continue  # paper-level scalar
        for cell in _cells(val):
            assert isinstance(cell, list)
            if field in GENDER:
                assert len(cell) in (1, 3), f"{fname}:{field} gender cell must be 1 or 3 long"
            else:
                # non-gender: usually 1, but multi-value categoricals (e.g. Country) allowed
                assert len(cell) >= 1


def test_swami2008_total_analytic_age_bmi_are_absent():
    import json
    from pathlib import Path

    d = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "target_values"
            / "1Swami2008Factor.json"
        ).read_text()
    )
    tkey = "Study 1 - Total analytic sample"
    # paper reports age/BMI only per ethnic subgroup → total is absent (null)
    assert all(v is None for v in d["Mean age of participants"][tkey])
    assert all(v is None for v in d["Mean BMI of participants"][tkey])
    # correlation IS reported at total level → still present (not absent)
    assert d["Correlation between body appreciation and BMI"][tkey] is not None
