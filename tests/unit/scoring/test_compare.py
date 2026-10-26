"""Tests for the extraction scorer."""

from __future__ import annotations

from mag.scoring.compare import align_samples, score

# Fixture uses normalized labels; extracted uses paper-faithful labels.
TARGET = {
    "Author": "Tylka",
    "Number of studies": 3,
    "Sample": {
        "Study 1 - college sample": [675, 367, 308],
        "Study 2 - community sample": [317, 150, 167],
    },
    "Mean age of participants": {
        "Study 1 - college sample": [20.34],
        "Study 2 - community sample": [32.89],
    },
    "Mean BMI of participants": {
        "Study 1 - college sample": [24.6156, 24.21, 25.02],
        "Study 2 - community sample": None,  # absent in fixture
    },
}
EXTRACTED = {
    "Author": "Tylka",
    "Number of studies": 3,
    "Sample": {
        "Study 1 - 675 participants": [675, 367, 308],
        "Study 2 - MTurk community participants": [317, 150, 167],
    },
    "Mean age of participants": {
        "Study 1 - 675 participants": [20.34],
        "Study 2 - MTurk community participants": [33.0],  # wrong (32.89 vs 33.0, diff 0.11 > 0.05)
    },
    "Mean BMI of participants": {
        "Study 1 - 675 participants": [24.5796, 24.21, 25.02],  # total within 0.05 of 24.6156
        "Study 2 - MTurk community participants": [],  # absent
    },
}


def test_align_samples_by_study_index_and_total():
    mapping = align_samples(EXTRACTED, TARGET)
    assert mapping["Study 1 - college sample"] == "Study 1 - 675 participants"
    assert mapping["Study 2 - community sample"] == "Study 2 - MTurk community participants"


def test_paper_field_correct():
    rep = score(EXTRACTED, TARGET)
    assert rep["per_field"]["Author"] == {"correct": 1, "incorrect": 0, "missing": 0}
    assert rep["per_field"]["Number of studies"]["correct"] == 1


def test_sample_field_all_correct():
    rep = score(EXTRACTED, TARGET)
    assert rep["per_field"]["Sample"] == {"correct": 2, "incorrect": 0, "missing": 0}


def test_numeric_tolerance_and_incorrect():
    rep = score(EXTRACTED, TARGET, tol=0.05)
    age = rep["per_field"]["Mean age of participants"]
    # Study 1 within tol → correct; Study 2 33.0 vs 32.89 (0.11) → incorrect
    assert age == {"correct": 1, "incorrect": 1, "missing": 0}


def test_absent_target_cell_not_counted():
    rep = score(EXTRACTED, TARGET, tol=0.05)
    bmi = rep["per_field"]["Mean BMI of participants"]
    # Study 1 total 24.5796 within 0.05 of 24.6156 → correct; Study 2 fixture is null → skipped
    assert bmi == {"correct": 1, "incorrect": 0, "missing": 0}


def test_totals_and_metrics():
    rep = score(EXTRACTED, TARGET, tol=0.05)
    t = rep["totals"]
    # correct: Author1 + NumStudies1 + Sample2 + Age1 + BMI1 = 6; incorrect: Age1 = 1; missing: 0
    assert t["correct"] == 6 and t["incorrect"] == 1 and t["missing"] == 0
    assert abs(t["precision"] - 6 / 7) < 1e-9
    assert t["recall"] == 1.0


def test_same_study_same_total_collision_does_not_misalign():
    target = {
        "Sample": {
            "Study 1 - sample A": [300, 150, 150],
            "Study 1 - sample B": [300, 160, 140],
        },
        "Mean age of participants": {
            "Study 1 - sample A": [20.0],
            "Study 1 - sample B": [40.0],
        },
    }
    extracted = {
        "Sample": {
            "Study 1 - x": [300, 150, 150],
            "Study 1 - y": [300, 160, 140],
        },
        "Mean age of participants": {
            "Study 1 - x": [20.0],
            "Study 1 - y": [40.0],
        },
    }
    mapping = align_samples(extracted, target)
    # (study 1, total 300) is ambiguous → both target samples unmatched, not mis-aligned
    assert mapping["Study 1 - sample A"] is None
    assert mapping["Study 1 - sample B"] is None
    rep = score(extracted, target)
    # both Sample cells unmatched → counted as missing, not falsely correct/incorrect
    assert rep["per_field"]["Sample"] == {"correct": 0, "incorrect": 0, "missing": 2}
    assert rep["per_field"]["Mean age of participants"] == {
        "correct": 0,
        "incorrect": 0,
        "missing": 2,
    }


def test_any_of_cell_matches_either_alternative():
    from mag.scoring.compare import score

    target = {
        "Sample": {"Study 1 - total": [591]},
        "Correlation between body appreciation and BMI": {
            "Study 1 - total": {"any_of": [[-0.135, -0.135, None], [-0.24, -0.24, None]]}
        },
    }
    extracted = {
        "Sample": {"Study 1 - total": [591]},
        "Correlation between body appreciation and BMI": {"Study 1 - total": [-0.24, -0.24, None]},
    }
    rep = score(extracted, target, tol=0.05)
    corr = rep["per_field"]["Correlation between body appreciation and BMI"]
    assert corr == {"correct": 1, "incorrect": 0, "missing": 0}


def test_any_of_cell_counts_incorrect_when_neither_matches():
    from mag.scoring.compare import score

    target = {
        "Sample": {"Study 1 - total": [591]},
        "Correlation between body appreciation and BMI": {
            "Study 1 - total": {"any_of": [[-0.135, -0.135, None], [-0.24, -0.24, None]]}
        },
    }
    extracted = {
        "Sample": {"Study 1 - total": [591]},
        "Correlation between body appreciation and BMI": {"Study 1 - total": [0.99, 0.99, None]},
    }
    rep = score(extracted, target, tol=0.05)
    corr = rep["per_field"]["Correlation between body appreciation and BMI"]
    assert corr == {"correct": 0, "incorrect": 1, "missing": 0}


def test_field_tol_overrides_global_for_one_field():
    from mag.scoring.compare import score

    target = {
        "Sample": {"Study 1 - s": [100]},
        "Percentage of college or higher of participants": {"Study 1 - s": [68.8]},
    }
    extracted = {
        "Sample": {"Study 1 - s": [100]},
        "Percentage of college or higher of participants": {"Study 1 - s": [68.95]},  # 0.15 off
    }
    strict = score(extracted, target, tol=0.05)
    assert strict["per_field"]["Percentage of college or higher of participants"]["incorrect"] == 1
    loose = score(
        extracted,
        target,
        tol=0.05,
        field_tol={"Percentage of college or higher of participants": 0.2},
    )
    assert loose["per_field"]["Percentage of college or higher of participants"]["correct"] == 1
