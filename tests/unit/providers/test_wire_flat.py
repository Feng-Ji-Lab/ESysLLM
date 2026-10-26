"""build_flat_field_schema for paper-scope aggregation."""

from __future__ import annotations

from mag.providers._wire import build_flat_field_schema


def test_flat_schema_scalar_value_and_reasoning():
    s = build_flat_field_schema({"name": "Author", "type": "string"})
    props = s["properties"]
    assert set(props) == {"value", "reasoning"}
    assert s["required"] == ["value", "reasoning"]
    # value allows the scalar type or the "None" sentinel
    assert any(o.get("enum") == ["None"] for o in props["value"]["anyOf"])


def test_flat_schema_enum_carries_allowed_values():
    s = build_flat_field_schema(
        {
            "name": "Publication type",
            "type": "enum_or_none",
            "allowed_values": ["journal articles", "dissertation"],
        }
    )
    enum_member = next(
        o for o in s["properties"]["value"]["anyOf"] if o.get("enum") and o["enum"] != ["None"]
    )
    assert enum_member["enum"] == ["journal articles", "dissertation"]


def test_flat_schema_integer_or_string():
    s = build_flat_field_schema({"name": "Year", "type": "integer_or_string"})
    types_present = {o.get("type") for o in s["properties"]["value"]["anyOf"]}
    assert {"integer", "string"} <= types_present
