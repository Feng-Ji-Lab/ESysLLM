"""Tests for aggregation prompt builders (prose sourced from the bundle PromptPack)."""

from __future__ import annotations

from mag.extraction.aggregate_prompts import (
    build_census_prompts,
    build_field_agg_prompts,
    build_flat_agg_prompts,
)
from mag.skills.loader import Skill

NAMING = Skill(
    name="study_naming", activates_on=["aggregator"], body="Name samples exactly as written."
)
BAS2 = Skill(
    name="bas2_over_bas",
    activates_on=["aggregator"],
    applies_to=["Assessment of BA"],
    body="Prefer BAS-2.",
)


def test_census_prompt_includes_naming_rule_and_candidates(prompts):
    sysp, userp = build_census_prompts(
        sample_candidates_text='[0] value={"Study 1": [675]}', skills=[NAMING], prompts=prompts
    )
    assert "Name samples exactly as written." in sysp
    assert "distinct sample" in sysp.lower()
    assert "675" in userp


def test_census_prompt_has_total_sample_rule(prompts):
    sysp, _ = build_census_prompts(sample_candidates_text="x", skills=[], prompts=prompts)
    assert "analytic" in sysp.lower()  # total/analytic sample rule (Part 3)


def test_field_prompt_lists_fixed_sample_keys(prompts):
    sysp, userp = build_field_agg_prompts(
        field={"name": "Sample", "gender_specific": True, "definition": "n [total, female, male]"},
        sample_keys=["Study 1 - college sample", "Study 2 - community sample"],
        candidates_text="[0] value=...",
        skills=[],
        prompts=prompts,
    )
    assert "Study 1 - college sample" in userp
    assert "Study 2 - community sample" in userp
    assert "n [total, female, male]" in sysp


def test_field_prompt_injects_only_applicable_skills(prompts):
    sysp, _ = build_field_agg_prompts(
        field={"name": "Assessment of BA", "definition": "d"},
        sample_keys=["Study 1"],
        candidates_text="c",
        skills=[BAS2, NAMING],
        prompts=prompts,
    )
    assert "Prefer BAS-2." in sysp
    assert "Name samples exactly as written." in sysp


def test_field_prompt_gender_shape_is_triple(prompts):
    sysp, _ = build_field_agg_prompts(
        field={"name": "Sample", "gender_specific": True, "definition": "d"},
        sample_keys=["Study 1"],
        candidates_text="c",
        skills=[],
        prompts=prompts,
    )
    assert "[total, female, male]" in sysp
    assert "SINGLE-element" not in sysp


def test_field_prompt_nongender_shape_is_single(prompts):
    sysp, _ = build_field_agg_prompts(
        field={"name": "Mean age of participants", "gender_specific": False, "definition": "d"},
        sample_keys=["Study 1"],
        candidates_text="c",
        skills=[],
        prompts=prompts,
    )
    assert "SINGLE-element" in sysp


def test_field_prompt_has_cautious_placement_guidance(prompts):
    sysp, _ = build_field_agg_prompts(
        field={"name": "Sample", "gender_specific": True, "definition": "d"},
        sample_keys=["Study 1"],
        candidates_text="c",
        skills=[],
        prompts=prompts,
    )
    assert "PLACEMENT" in sysp
    assert "combined sample" in sysp.lower()
    assert "from=" in sysp


def test_field_prompt_has_one_value_per_study_guidance(prompts):
    from mag.extraction.aggregate_prompts import build_field_agg_prompts

    sysp, _ = build_field_agg_prompts(
        field={"name": "Survey method", "gender_specific": False, "definition": "d"},
        sample_keys=["Study 1", "Study 2"],
        candidates_text="c",
        skills=[],
        prompts=prompts,
    )
    assert "one value per study" in sysp.lower()


def test_field_prompt_has_study_anchor_and_constant_and_no_synth_total(prompts):
    from mag.extraction.aggregate_prompts import build_field_agg_prompts

    sysp, _ = build_field_agg_prompts(
        field={"name": "Survey method", "gender_specific": False, "definition": "d"},
        sample_keys=["Study 1", "Study 2"],
        candidates_text="c",
        skills=[],
        prompts=prompts,
    )
    low = sysp.lower()
    assert "study=" in sysp  # place-by-study anchor (A.2)
    assert "study-wide" in low  # constant distribution (B)
    assert "synthesize" in low or "never average" in low  # no-synth-total (D)


def test_flat_prompt_is_paper_level(prompts):
    sysp, userp = build_flat_agg_prompts(
        field={"name": "Author", "definition": "author line"},
        candidates_text="[0] value=...",
        skills=[],
        prompts=prompts,
    )
    assert "paper-level field" in sysp
    assert "Author" in userp
    assert '"None"' in sysp  # code-owned None sentinel still present
