#!/usr/bin/env python
# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)
"""
test_dashboard.py – Edge-case tests for build_dashboard.py comparison logic.

Run:
    conda activate pytorch
    python test_dashboard.py
"""

import sys
import json
import os
import tempfile
import shutil

# Import from build_dashboard
from build_dashboard import (
    is_none_like,
    is_gt_val_empty,
    normalize_val,
    flatten_values,
    get_study_buckets,
    norm_list,
    multiset_eq,
    values_subset,
    encode_country,
    encode_enum,
    encode_extracted_for_comparison,
    compare_field,
    match_gt_paper,
    load_results,
    build_comparison,
)


def formatBestIndices_py(indices):
    """Python equivalent of the JS formatBestIndices."""
    if not indices:
        return "(none)"
    s = sorted(indices)
    ranges = []
    start = end = s[0]
    for i in range(1, len(s)):
        if s[i] == end + 1:
            end = s[i]
        else:
            ranges.append(str(start) if start == end else f"{start}-{end}")
            start = end = s[i]
    ranges.append(str(start) if start == end else f"{start}-{end}")
    return ", ".join(ranges)


def test_extract_value_is_list():
    """Edge case 1: extract_value is a plain list (e.g., Publication type)."""
    ext_data = {
        "extract_value": ["journal articles"],
        "best_indices": [0, 1, 2],
        "reason": "test"
    }
    gt_val = {"study": [1]}  # 1 = journal articles in ENUM_MAPPING
    result = compare_field("Publication type", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: extract_value as list (Publication type)")


def test_extract_value_is_dict():
    """Edge case 1b: extract_value is a dict (most fields)."""
    ext_data = {
        "extract_value": {"Single study": ["community"]},
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {"study": [3]}  # 3 = community in ENUM_MAPPING
    result = compare_field("Source of sample", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: extract_value as dict (Source of sample)")


def test_missing_field_in_paper():
    """Edge case 2: A field is missing from a paper's final_results."""
    # If a paper doesn't have the field at all, compare_field shouldn't
    # be called for it. But build_comparison should mark it 'none'.
    papers = {
        "paper1": {
            "Country": {
                "extract_value": {"Study 1": ["United States"]},
                "best_indices": [0],
                "reason": "test"
            }
            # "Sample" is missing
        }
    }
    gt_data = {
        "paper1": {
            "Country": {"study": [1]},
            "Sample": {"male": {"study": [100]}, "female": {"study": [200]}, "total": {"study": []}}
        }
    }
    comp = build_comparison(papers, ["Country", "Sample"], gt_data)
    assert comp["paper1"]["Country"] == "full", f"Country: expected 'full', got '{comp['paper1']['Country']}'"
    assert comp["paper1"]["Sample"] == "none", f"Sample: expected 'none', got '{comp['paper1']['Sample']}'"
    print("  PASS: missing field marked as 'none'")


def test_gender_with_empty_genders():
    """Edge case 3: extract_value_by_gender present but some genders empty/none."""
    ext_data = {
        "extract_value": {"Single study": ["326"]},
        "extract_value_by_gender": {
            "male": {"Single study": []},
            "female": {"Single study": ["326"]},
            "other": {"Single study": []},
            "total": {"Single study": ["326"]}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": ["none"]},
        "female": {"study": [326]},
        "total": {"study": []}
    }
    result = compare_field("Sample", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: gender fields with empty/none genders")


def test_total_mismatch_with_extract_value():
    """Edge case 4: extract_value_by_gender.total differs from extract_value."""
    ext_data = {
        "extract_value": {"Study 1": ["500"]},
        "extract_value_by_gender": {
            "male": {"Study 1": ["200"]},
            "female": {"Study 1": ["300"]},
            "other": {"Study 1": []},
            "total": {"Study 1": ["500"]}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": [200]},
        "female": {"study": [300]},
        "total": {"study": [500]}
    }
    result = compare_field("Sample", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: total/extract_value mismatch (values still match GT)")


def test_best_indices_ranges():
    """Edge case 5: best_indices formatting with multiple disjoint ranges."""
    indices = [0, 1, 2, 3, 4, 6, 7, 8, 11]
    formatted = formatBestIndices_py(indices)
    assert formatted == "0-4, 6-8, 11", f"Expected '0-4, 6-8, 11', got '{formatted}'"

    # Single index
    assert formatBestIndices_py([5]) == "5"
    # Empty
    assert formatBestIndices_py([]) == "(none)"
    # Consecutive
    assert formatBestIndices_py([0, 1, 2]) == "0-2"
    # Disjoint singles
    assert formatBestIndices_py([1, 3, 5]) == "1, 3, 5"
    print("  PASS: best_indices range formatting")


def test_gt_missing_for_paper():
    """Edge case 6: ground truth missing for a paper entirely."""
    papers = {
        "unknown_paper": {
            "Country": {
                "extract_value": {"Study 1": ["Japan"]},
                "best_indices": [0],
                "reason": "test"
            }
        }
    }
    gt_data = {
        "other_paper": {"Country": {"study": [4]}}
    }
    comp = build_comparison(papers, ["Country"], gt_data)
    assert comp["unknown_paper"] == {}, f"Expected empty dict, got {comp['unknown_paper']}"
    print("  PASS: ground truth missing for paper")


def test_numeric_strings_vs_numbers():
    """Edge case 7: numeric strings ('326') vs numbers (326) comparison."""
    ext_data = {
        "extract_value": {"Single study": ["49.14"]},
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": ["none"]},
        "female": {"study": [49.14]},
        "total": {"study": []}
    }
    result = compare_field("Mean age of participants", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: numeric string vs number comparison")


def test_country_encoding():
    """Test country encoding to continent codes."""
    codes = encode_country("Saudi Arabia")
    assert codes == [4], f"Expected [4], got {codes}"

    codes = encode_country("United States")
    assert codes == [1], f"Expected [1], got {codes}"

    codes = encode_country("Netherlands")
    assert codes == [2], f"Expected [2], got {codes}"
    print("  PASS: country encoding")


def test_enum_encoding():
    """Test enum value encoding."""
    r = encode_enum("Publication type", "journal articles")
    assert r == 1.0, f"Expected 1.0, got {r}"

    r = encode_enum("Survey method", "paper-and-pencil")
    assert r == 2.0, f"Expected 2.0, got {r}"

    r = encode_enum("Assessment of BA", "BAS")
    assert r == 1.0, f"Expected 1.0, got {r}"
    print("  PASS: enum encoding")


def test_partial_match():
    """Test partial match: GT values are subset of extracted values."""
    ext_data = {
        "extract_value": {"Study 1": ["100", "200"], "Study 2": ["300"]},
        "best_indices": [0],
        "reason": "test"
    }
    # GT only expects 100, which is in extracted
    gt_val = {"study": [100]}
    result = compare_field("Sample", ext_data, gt_val)
    assert result == "partial", f"Expected 'partial', got '{result}'"
    print("  PASS: partial match detection")


def test_paper_matching():
    """Test paper ID matching with different formats."""
    gt_data = {
        "1Al Otaibi2018": {"Country": {"study": [4]}},
        "1Swami2008Factor structure of the Body Apprecia": {"Country": {"study": [2]}},
    }

    # Exact match
    assert match_gt_paper("1Al Otaibi2018", gt_data) is not None
    # Prefix match
    assert match_gt_paper("1Swami2008Factor structure of the Body Appreciation Scale", gt_data) is not None
    # No match
    assert match_gt_paper("nonexistent", gt_data) is None
    print("  PASS: paper matching (exact, prefix, no match)")


def test_multi_study_comparison():
    """Test comparison with multi-study papers."""
    ext_data = {
        "extract_value": {"Study 1": ["246"], "Study 2": ["105"]},
        "extract_value_by_gender": {
            "male": {"Study 1": ["142"], "Study 2": ["0"]},
            "female": {"Study 1": ["104"], "Study 2": ["105"]},
            "other": {"Study 1": [], "Study 2": []},
            "total": {"Study 1": ["246"], "Study 2": ["105"]}
        },
        "best_indices": [0, 1],
        "reason": "test"
    }
    # GT has values that match study 1
    gt_val = {
        "male": {"study": [142]},
        "female": {"study": [104]},
        "total": {"study": []}
    }
    result = compare_field("Sample", ext_data, gt_val)
    # GT male=[142] found in extracted male, GT female=[104] found in extracted female
    assert result in ("full", "partial"), f"Expected 'full' or 'partial', got '{result}'"
    print("  PASS: multi-study comparison")


def test_end_to_end_file_loading():
    """Test loading results from a temp directory structure."""
    tmpdir = tempfile.mkdtemp()
    try:
        # Create paper folder
        paper_dir = os.path.join(tmpdir, "TestPaper2024")
        os.makedirs(paper_dir)

        final_results = {
            "Country": {
                "extract_value": {"Study 1": ["Japan"]},
                "best_indices": [0, 1],
                "reason": "Test reason"
            },
            "Publication type": {
                "extract_value": ["journal articles"],
                "best_indices": [0],
                "reason": "Test"
            },
            "Number of studies": {
                "extract_value": [1],
                "best_indices": [0],
                "reason": "Test"
            }
        }
        with open(os.path.join(paper_dir, "final_results.json"), "w") as f:
            json.dump(final_results, f)

        papers, all_fields = load_results(tmpdir)
        assert "TestPaper2024" in papers
        assert "Country" in all_fields
        assert "Publication type" in all_fields
        assert "Number of studies" not in all_fields  # should be skipped
        print("  PASS: end-to-end file loading")
    finally:
        shutil.rmtree(tmpdir)


def test_single_gender_gt_full_match():
    """Partial ground truth (female only): full match if female values match."""
    ext_data = {
        "extract_value": {"Single study": ["326"]},
        "extract_value_by_gender": {
            "male": {"Single study": []},
            "female": {"Single study": ["326"]},
            "other": {"Single study": []},
            "total": {"Single study": ["326"]}
        },
        "best_indices": [0],
        "reason": "test"
    }
    # GT: only female has value, male and total are empty
    gt_val = {
        "male": {"study": ["none"]},
        "female": {"study": [326]},
        "total": {"study": []}
    }
    result = compare_field("Sample", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: single-gender GT (female only) → full match")


def test_single_gender_gt_male_only():
    """Partial ground truth (male only): full match if male values match."""
    ext_data = {
        "extract_value": {"Single study": ["200"]},
        "extract_value_by_gender": {
            "male": {"Single study": ["200"]},
            "female": {"Single study": []},
            "other": {"Single study": []},
            "total": {"Single study": ["200"]}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": [200]},
        "female": {"study": []},
        "total": {"study": []}
    }
    result = compare_field("Sample", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: single-gender GT (male only) → full match")


def test_gt_total_only_fallback_to_extract_value():
    """Total ground truth only: full match if extracted total matches ground truth total."""
    ext_data = {
        "extract_value": {"Single study": ["50.5"]},
        "extract_value_by_gender": {
            "male": {"Single study": []},
            "female": {"Single study": []},
            "other": {"Single study": []},
            "total": {"Single study": []}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": []},
        "female": {"study": []},
        "total": {"study": [50.5]}
    }
    result = compare_field("Mean age of participants", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: GT total-only, fallback to extract_value → full match")


def test_gt_total_only_no_ext_gender_at_all():
    """Total ground truth only (no gender extraction): full match if extracted main value matches."""
    ext_data = {
        "extract_value": {"Single study": ["100"]},
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": []},
        "female": {"study": []},
        "total": {"study": [100]}
    }
    result = compare_field("Sample", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: GT total-only, no ext gender data → full match")


def test_gt_total_only_mismatch():
    """Total ground truth only: no match if extracted value differs."""
    ext_data = {
        "extract_value": {"Single study": ["999"]},
        "extract_value_by_gender": {
            "male": {"Single study": []},
            "female": {"Single study": []},
            "other": {"Single study": []},
            "total": {"Single study": []}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": []},
        "female": {"study": []},
        "total": {"study": [100]}
    }
    result = compare_field("Sample", ext_data, gt_val)
    assert result == "none", f"Expected 'none', got '{result}'"
    print("  PASS: GT total-only, extract_value mismatch → none")


def test_percentage_gt_proportion_to_percent():
    """Percentage field: GT stores 0.334 (proportion), extracted stores 33.4 (percent).
    Should be full match after *100 conversion."""
    ext_data = {
        "extract_value": {"Single study": ["33.4"]},
        "extract_value_by_gender": {
            "male": {"Single study": []},
            "female": {"Single study": ["33.4"]},
            "other": {"Single study": []},
            "total": {"Single study": ["33.4"]}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": ["none"]},
        "female": {"study": [0.334]},
        "total": {"study": []}
    }
    result = compare_field("Percentage of college or higher of participants", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: percentage GT proportion (0.334) matches extracted (33.4)")


def test_percentage_gt_white():
    """Percent of white: GT stores 0.9032, extracted stores 90.32."""
    ext_data = {
        "extract_value": {"Single study": ["90.32"]},
        "extract_value_by_gender": {
            "male": {"Single study": []},
            "female": {"Single study": []},
            "other": {"Single study": []},
            "total": {"Single study": ["90.32"]}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": []},
        "female": {"study": []},
        "total": {"study": [0.9032]}
    }
    result = compare_field("Percent of white in participants", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: percent-of-white GT proportion (0.9032) matches extracted (90.32)")


def test_percentage_does_not_affect_correlation():
    """Correlation field must NOT be rescaled — values like -0.237 stay as-is."""
    ext_data = {
        "extract_value": {"Single study": ["-0.237"]},
        "extract_value_by_gender": {
            "male": {"Single study": []},
            "female": {"Single study": ["-0.237"]},
            "other": {"Single study": []},
            "total": {"Single study": ["-0.237"]}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": ["none"]},
        "female": {"study": [-0.237]},
        "total": {"study": []}
    }
    result = compare_field("Correlation between body appreciation and BMI", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: correlation field NOT rescaled (-0.237 matches -0.237)")


def test_percentage_gt_value_is_1():
    """GT value of 1 (=100%) should be rescaled to 100 for percentage fields."""
    ext_data = {
        "extract_value": {"Single study": ["100"]},
        "extract_value_by_gender": {
            "male": {"Single study": []},
            "female": {"Single study": ["100"]},
            "other": {"Single study": []},
            "total": {"Single study": ["100"]}
        },
        "best_indices": [0],
        "reason": "test"
    }
    gt_val = {
        "male": {"study": []},
        "female": {"study": [1]},
        "total": {"study": []}
    }
    # GT=1 → 1*100=100, extracted="100" → full match
    result = compare_field("Percentage of college or higher of participants", ext_data, gt_val)
    assert result == "full", f"Expected 'full', got '{result}'"
    print("  PASS: percentage GT value 1 → 100 full match")


def test_empty_gt_missing_field_full_match():
    """Empty GT + field missing from extracted → full match."""
    papers = {
        "paper1": {
            "Country": {
                "extract_value": {"Study 1": ["United States"]},
                "best_indices": [0],
                "reason": "test"
            }
            # "Percent of white in participants" is missing entirely
        }
    }
    gt_data = {
        "paper1": {
            "Country": {"study": [1]},
            "Percent of white in participants": {
                "male": {"study": []},
                "female": {"study": []},
                "total": {"study": ["none"]}
            }
        }
    }
    comp = build_comparison(papers, ["Country", "Percent of white in participants"], gt_data)
    assert comp["paper1"]["Country"] == "full"
    assert comp["paper1"]["Percent of white in participants"] == "full", \
        f"Expected 'full', got '{comp['paper1']['Percent of white in participants']}'"
    print("  PASS: empty GT + missing field → full match")


def test_nonempty_gt_missing_field_none():
    """Non-empty GT + field missing from extracted → none."""
    papers = {
        "paper1": {
            "Country": {
                "extract_value": {"Study 1": ["Japan"]},
                "best_indices": [0],
                "reason": "test"
            }
        }
    }
    gt_data = {
        "paper1": {
            "Country": {"study": [4]},
            "Sample": {
                "male": {"study": [100]},
                "female": {"study": [200]},
                "total": {"study": []}
            }
        }
    }
    comp = build_comparison(papers, ["Country", "Sample"], gt_data)
    assert comp["paper1"]["Sample"] == "none", \
        f"Expected 'none', got '{comp['paper1']['Sample']}'"
    print("  PASS: non-empty GT + missing field → none")


def test_is_gt_val_empty_various():
    """Test is_gt_val_empty helper with various inputs."""
    # Empty gender dict
    assert is_gt_val_empty({
        "male": {"study": []},
        "female": {"study": ["none"]},
        "total": {"study": []}
    }) == True

    # Non-empty gender dict
    assert is_gt_val_empty({
        "male": {"study": [100]},
        "female": {"study": []},
        "total": {"study": []}
    }) == False

    # Empty list
    assert is_gt_val_empty({"study": []}) == True
    assert is_gt_val_empty({"study": ["none"]}) == True

    # Non-empty flat
    assert is_gt_val_empty({"study": [1]}) == False

    # None
    assert is_gt_val_empty(None) == True

    print("  PASS: is_gt_val_empty helper works correctly")


def main():
    print("Running dashboard edge-case tests...\n")
    tests = [
        test_extract_value_is_list,
        test_extract_value_is_dict,
        test_missing_field_in_paper,
        test_gender_with_empty_genders,
        test_total_mismatch_with_extract_value,
        test_best_indices_ranges,
        test_gt_missing_for_paper,
        test_numeric_strings_vs_numbers,
        test_country_encoding,
        test_enum_encoding,
        test_partial_match,
        test_paper_matching,
        test_multi_study_comparison,
        test_end_to_end_file_loading,
        test_single_gender_gt_full_match,
        test_single_gender_gt_male_only,
        test_gt_total_only_fallback_to_extract_value,
        test_gt_total_only_no_ext_gender_at_all,
        test_gt_total_only_mismatch,
        test_percentage_gt_proportion_to_percent,
        test_percentage_gt_white,
        test_percentage_does_not_affect_correlation,
        test_percentage_gt_value_is_1,
        test_empty_gt_missing_field_full_match,
        test_nonempty_gt_missing_field_none,
        test_is_gt_val_empty_various,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
    if failed:
        sys.exit(1)
    else:
        print("All tests passed!")


if __name__ == "__main__":
    main()
