"""The shipped bas-bmi schema must match the per-field shape _wire expects."""

from __future__ import annotations

import json
from pathlib import Path

from mag.providers._wire import build_section_schema

FIELDS = json.loads(Path("schemas/bas-bmi/fields.json").read_text())

GENDER_SPECIFIC = {
    "Sample",
    "Mean BMI of participants",
    "Correlation between body appreciation and BMI",
}
PAPER_SCOPE = {"Author", "Year", "Publication type", "Number of studies"}


def test_every_field_has_scope_and_gender_flag():
    for f in FIELDS["fields"]:
        assert f["scope"] in ("paper", "sample"), f["name"]
        assert isinstance(f.get("gender_specific", False), bool), f["name"]


def test_gender_specific_set_matches_target_spec():
    got = {f["name"] for f in FIELDS["fields"] if f.get("gender_specific")}
    assert got == GENDER_SPECIFIC


def test_paper_scope_set():
    got = {f["name"] for f in FIELDS["fields"] if f["scope"] == "paper"}
    assert got == PAPER_SCOPE


def test_gender_fields_declare_total_female_male_order():
    for f in FIELDS["fields"]:
        if f.get("gender_specific"):
            assert f["position_order"] == ["total", "female", "male"], f["name"]


def test_wire_builder_keeps_schema_flat_no_gender_object():
    # Gender breakdown is captured positionally in the value list, not a separate
    # object — required to stay under Vertex AI's structured-output state budget.
    schema = build_section_schema(FIELDS)
    for name in schema["properties"]:
        assert "extract_value_by_gender" not in schema["properties"][name]["properties"], name


def test_skill_hooks_present():
    by_name = {f["name"]: f for f in FIELDS["fields"]}
    assert (
        "infer_college_sample_100"
        in by_name["Percentage of college or higher of participants"]["skills"]
    )
    assert "compute_weighted_mean_total" in by_name["Mean BMI of participants"]["skills"]


def test_flipped_fields_definitions_are_degendered():
    by_name = {f["name"]: f for f in FIELDS["fields"]}
    for name in ("Survey method", "Source of sample", "Assessment of BA", "Assessment of BMI"):
        assert by_name[name]["gender_specific"] is False
        assert "total, female, male" not in by_name[name]["definition"]
        assert "position_order" not in by_name[name]
