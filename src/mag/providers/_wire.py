"""v1-shaped wire schemas the LLM emits, plus a helper to restore them.

Design rules proven necessary in Phase 1.9 and R0.5:
- dynamic-key dicts use [{key, value}] arrays, NOT additionalProperties (Gemini rejects it)
- missing values use the "None" string sentinel, NOT JSON null (smaller state space)
- evidence is a free-text string + a block_id string (R0.5 F1: Gemini emits block ids verbatim)
"""

from __future__ import annotations

from typing import Any

# Shared by reference across all built schemas; treat built schemas as immutable
# (do NOT mutate a schema dict in place, or you corrupt every other schema's sentinel).
NONE_SENTINEL: dict[str, Any] = {"type": "string", "enum": ["None"]}


def _item_schema(items_type: str, allowed: list | None) -> dict[str, Any]:
    if items_type == "integer":
        return {"type": "integer"}
    if items_type == "number":
        return {"type": "number"}
    if items_type == "enum" and allowed:
        return {"type": "string", "enum": allowed}
    return {"type": "string"}


def _object_value_schema(items_type: str, allowed: list | None) -> dict[str, Any]:
    return {
        "anyOf": [
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "sample name as written here"},
                        "value": {"type": "array", "items": _item_schema(items_type, allowed)},
                    },
                    "required": ["key", "value"],
                },
            },
            NONE_SENTINEL,
        ]
    }


def _scalar_value_schema(ftype: str, allowed: list | None) -> dict[str, Any]:
    if ftype == "integer_or_string":
        return {"anyOf": [{"type": "integer"}, {"type": "string"}, NONE_SENTINEL]}
    if ftype == "integer":
        base: dict[str, Any] = {"type": "integer"}
    elif ftype in ("number", "number_percent"):
        base = {"type": "number"}
    elif ftype in ("enum", "enum_or_none") and allowed:
        base = {"type": "string", "enum": allowed}
    else:
        base = {"type": "string"}
    return {"anyOf": [base, NONE_SENTINEL]}


def _value_schema(field: dict) -> dict[str, Any]:
    if field.get("type") == "object":
        return _object_value_schema(field.get("items_type", "string"), field.get("allowed_values"))
    return _scalar_value_schema(field.get("type", "string"), field.get("allowed_values"))


def build_section_schema(fields_cfg: dict) -> dict[str, Any]:
    """Schema for one per-section extraction call (all fields at once).

    Gender-specific fields do NOT get a separate ``extract_value_by_gender``
    object: the gender breakdown lives positionally in the value list
    (``[total, female, male]``, per the field's ``position_order`` and the
    prompt). Keeping the schema flat is also required to stay under Vertex AI's
    structured-output state budget — a per-field 4-gender sub-object across
    several fields trips ``400 INVALID_ARGUMENT: too many states for serving``.
    """
    props: dict[str, Any] = {}
    for f in fields_cfg["fields"]:
        props[f["name"]] = {
            "type": "object",
            "properties": {
                "extract_value": _value_schema(f),
                "evidence_source": {"type": "string"},
                "block_id": {"type": "string"},
                "warning": {"type": "string"},
            },
            "required": ["extract_value", "evidence_source", "block_id", "warning"],
        }
    return {"type": "object", "properties": props, "required": list(props.keys())}


def build_sample_census_schema() -> dict[str, Any]:
    """Schema for the Stage 2a sample-census call (one per paper)."""
    return {
        "type": "object",
        "properties": {
            "samples": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "study_index": {"type": "integer"},
                        "sample_label": {"type": "string"},
                        "total_n": {"type": "integer"},
                        "evidence": {"type": "string"},
                        "gender": {"type": "string", "enum": ["all_female", "all_male", "mixed"]},
                    },
                    "required": ["study_index", "sample_label", "total_n"],
                },
            }
        },
        "required": ["samples"],
    }


def build_field_aggregation_schema(field: dict, sample_keys: list[str]) -> dict[str, Any]:
    """Schema for one Stage 2b per-field aggregation call.

    `sample_keys` (from Stage 2a) constrain `sample_key` to the known set.
    """
    item = _item_schema(
        field.get("items_type", field.get("type", "string")), field.get("allowed_values")
    )
    sample_key_schema = (
        {"type": "string", "enum": sample_keys} if sample_keys else {"type": "string"}
    )
    return {
        "type": "object",
        "properties": {
            "resolved_samples": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sample_key": sample_key_schema,
                        # JSON null here (not the "None" string sentinel used in section/census
                        # schemas): aggregation values are positional [total, female, male] arrays
                        # where an absent slot is a real null, and inflate passes it through as None.
                        "values": {"type": "array", "items": {"anyOf": [item, {"type": "null"}]}},
                        "best_indices": {"type": "array", "items": {"type": "integer"}},
                        "reasoning": {"type": "string"},
                    },
                    "required": ["sample_key", "values", "best_indices", "reasoning"],
                },
            }
        },
        "required": ["resolved_samples"],
    }


def build_flat_field_schema(field: dict) -> dict[str, Any]:
    """Schema for aggregating a paper-scope field to a single value."""
    return {
        "type": "object",
        "properties": {
            "value": _scalar_value_schema(field.get("type", "string"), field.get("allowed_values")),
            "reasoning": {"type": "string"},
        },
        "required": ["value", "reasoning"],
    }


def restore_pairs(value: Any) -> Any:
    """Convert [{key, value}] arrays into {key: value} dicts; "None" → None; else passthrough."""
    if value == "None":
        return None
    if (
        isinstance(value, list)
        and value
        and all(isinstance(x, dict) and "key" in x and "value" in x for x in value)
    ):
        return {x["key"]: x["value"] for x in value}
    return value
