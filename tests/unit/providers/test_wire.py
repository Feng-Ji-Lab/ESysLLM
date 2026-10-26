"""Tests for the v1-shaped wire schema builders."""

from __future__ import annotations

from mag.providers._wire import (
    build_field_aggregation_schema,
    build_sample_census_schema,
    build_section_schema,
    restore_pairs,
)

FIELDS_CFG = {
    "version": 2,
    "fields": [
        {"name": "Author", "scope": "paper", "type": "string"},
        {
            "name": "Sample",
            "scope": "sample",
            "gender_specific": True,
            "type": "object",
            "items_type": "integer",
        },
        {
            "name": "Survey method",
            "scope": "sample",
            "type": "object",
            "items_type": "enum",
            "allowed_values": ["paper-and-pencil", "online"],
        },
    ],
}


def test_section_schema_top_level():
    s = build_section_schema(FIELDS_CFG)
    assert s["type"] == "object"
    assert set(s["properties"]) == {"Author", "Sample", "Survey method"}
    assert s["required"] == ["Author", "Sample", "Survey method"]


def test_section_field_has_block_id_and_evidence():
    s = build_section_schema(FIELDS_CFG)
    props = s["properties"]["Author"]["properties"]
    assert "evidence_source" in props
    assert "block_id" in props  # required by R0.5 F1
    assert props["block_id"] == {"type": "string"}


def test_object_field_uses_key_value_pairs_not_additionalproperties():
    s = build_section_schema(FIELDS_CFG)
    ev = s["properties"]["Sample"]["properties"]["extract_value"]
    # anyOf: [ array-of-{key,value} , "None" sentinel ]
    arr = next(o for o in ev["anyOf"] if o.get("type") == "array")
    item = arr["items"]
    assert item["type"] == "object"
    assert set(item["properties"]) == {"key", "value"}
    # no additionalProperties anywhere in the field schema
    assert "additionalProperties" not in str(s["properties"]["Sample"])


def test_none_sentinel_is_string_enum():
    s = build_section_schema(FIELDS_CFG)
    ev = s["properties"]["Author"]["properties"]["extract_value"]
    sentinels = [o for o in ev["anyOf"] if o.get("enum") == ["None"]]
    assert sentinels and sentinels[0]["type"] == "string"


def test_no_separate_gender_object_in_wire():
    # Gender breakdown lives positionally in the value list ([total, female, male]),
    # not a separate object — keeps the schema under Vertex's state budget.
    s = build_section_schema(FIELDS_CFG)
    for name in s["properties"]:
        assert "extract_value_by_gender" not in s["properties"][name]["properties"], name


def test_enum_items_carry_allowed_values():
    s = build_section_schema(FIELDS_CFG)
    ev = s["properties"]["Survey method"]["properties"]["extract_value"]
    arr = next(o for o in ev["anyOf"] if o.get("type") == "array")
    assert arr["items"]["properties"]["value"]["items"]["enum"] == ["paper-and-pencil", "online"]


def test_sample_census_schema():
    s = build_sample_census_schema()
    item = s["properties"]["samples"]["items"]
    assert set(item["required"]) == {"study_index", "sample_label", "total_n"}


def test_field_aggregation_schema_constrains_sample_keys():
    keys = ["Study 1 - college sample", "Study 2 - community sample"]
    s = build_field_aggregation_schema({"type": "number"}, keys)
    sk = s["properties"]["resolved_samples"]["items"]["properties"]["sample_key"]
    assert sk["enum"] == keys


def test_field_aggregation_schema_without_keys_is_plain_string():
    s = build_field_aggregation_schema({"type": "number"}, [])
    sk = s["properties"]["resolved_samples"]["items"]["properties"]["sample_key"]
    assert sk == {"type": "string"}


def test_restore_pairs_roundtrip():
    pairs = [{"key": "Study 1", "value": [675]}, {"key": "Study 2", "value": [263]}]
    assert restore_pairs(pairs) == {"Study 1": [675], "Study 2": [263]}


def test_restore_pairs_none_sentinel():
    assert restore_pairs("None") is None


def test_restore_pairs_passthrough_scalar():
    assert restore_pairs(2015) == 2015


def test_integer_or_string_is_three_way_anyof():
    s = build_section_schema(
        {"fields": [{"name": "Year", "scope": "paper", "type": "integer_or_string"}]}
    )
    ev = s["properties"]["Year"]["properties"]["extract_value"]
    types_present = {o.get("type") for o in ev["anyOf"]}
    assert {"integer", "string"} <= types_present
    assert any(o.get("enum") == ["None"] for o in ev["anyOf"])


def test_number_percent_maps_to_number():
    s = build_section_schema(
        {"fields": [{"name": "Pct", "scope": "sample", "type": "number_percent"}]}
    )
    ev = s["properties"]["Pct"]["properties"]["extract_value"]
    assert any(o.get("type") == "number" for o in ev["anyOf"])


def test_enum_or_none_uses_allowed_values():
    s = build_section_schema(
        {
            "fields": [
                {
                    "name": "PubType",
                    "scope": "paper",
                    "type": "enum_or_none",
                    "allowed_values": ["journal articles", "dissertation"],
                }
            ]
        }
    )
    ev = s["properties"]["PubType"]["properties"]["extract_value"]
    enum_member = next(o for o in ev["anyOf"] if o.get("enum") and o.get("enum") != ["None"])
    assert enum_member["enum"] == ["journal articles", "dissertation"]


def test_restore_pairs_empty_list_passthrough():
    assert restore_pairs([]) == []


def test_census_schema_has_optional_gender_enum():
    from mag.providers._wire import build_sample_census_schema

    item = build_sample_census_schema()["properties"]["samples"]["items"]
    assert item["properties"]["gender"]["enum"] == ["all_female", "all_male", "mixed"]
    assert "gender" not in item["required"]  # optional
