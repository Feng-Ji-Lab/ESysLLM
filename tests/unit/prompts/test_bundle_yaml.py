"""The shipped schema bundles load and carry the required guidance."""

from __future__ import annotations

from pathlib import Path

import pytest

from mag.prompts.loader import load_prompts

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("bundle", ["bas-bmi", "default"])
def test_bundle_loads(bundle):
    load_prompts(REPO / "schemas" / bundle)


def test_bas_bmi_carries_key_guidance():
    pack = load_prompts(REPO / "schemas" / "bas-bmi")
    # census recognizes a total/analytic sample (Part 3)
    assert "total" in pack.stage2.census_system.lower()
    assert "analytic" in pack.stage2.census_system.lower()
    # placement guidance survived the move from code
    assert "PLACEMENT" in pack.stage2.field_system
    assert "from=" in pack.stage2.field_system
    # effect-size guidance: correlations appear in results text
    assert "text" in pack.stage1.system.effect_size_guidance.lower()
    # shape strings
    assert "total, female, male" in pack.stage2.gender_shape
    assert "single" in pack.stage2.nongender_shape.lower()


def test_default_carries_shape_and_placement_guidance():
    pack = load_prompts(REPO / "schemas" / "default")
    assert "total, female, male" in pack.stage2.gender_shape
    assert "single" in pack.stage2.nongender_shape.lower()
    assert "PLACEMENT" in pack.stage2.field_system
    # default role must be domain-neutral (no BAS/BMI specifics)
    assert "BAS" not in pack.stage1.system.role
    assert "BMI" not in pack.stage1.system.role


def test_orphan_prompts_json_removed():
    assert not (REPO / "schemas" / "bas-bmi" / "prompts.json").exists()
    assert not (REPO / "schemas" / "default" / "prompts.json").exists()


def test_census_has_desegmentation_rules():
    pack = load_prompts(REPO / "schemas" / "bas-bmi")
    cs = pack.stage2.census_system.lower()
    assert "within-cell breakdown" in cs or "gender is a within" in cs  # gender not a sample
    assert "grand total" in cs or "grand-total" in cs  # no parent-total sibling
    assert "analytic" in cs  # total/analytic exception kept


def test_census_prompt_requests_gender():
    pack = load_prompts(REPO / "schemas" / "bas-bmi")
    assert "all_female" in pack.stage2.census_system


def test_stage1_has_serial_subgroup_and_multitable_and_sign():
    for bundle in ("bas-bmi", "default"):
        pack = load_prompts(REPO / "schemas" / bundle)
        naming = pack.stage1.system.sample_naming.lower()
        assert "per subgroup" in naming  # serial per-subgroup (C)
        assert "sub-table" in naming  # multi-table (D)
        assert "negative" in pack.stage1.system.effect_size_guidance.lower()  # prose sign (D)


def test_census_distinguishes_gender_from_nongender_subgroups():
    for bundle in ("bas-bmi", "default"):
        pack = load_prompts(REPO / "schemas" / bundle)
        cs = pack.stage2.census_system
        low = cs.lower()
        # gender within-cell rule is explicitly gender-only
        assert "only to gender" in low or "gender only" in low
        # non-gender stratified subgroups (ethnicity / region / etc.) addressed
        assert "ethnicity" in low or "ethnic" in low
        # two-pronged test conjunction
        assert "both" in low
        # demographic distribution alone does NOT split into samples
        assert "distribution" in low
        # total/analytic sample is ADDITIVE, not a replacement
        assert "in addition to" in low
        # analysis-only narrowed to procedural splits
        assert "procedural" in low


def test_census_bundles_remain_identical_after_refinement():
    a = load_prompts(REPO / "schemas" / "bas-bmi").stage2.census_system
    b = load_prompts(REPO / "schemas" / "default").stage2.census_system
    assert a == b, "census_system drifted between bundles"
