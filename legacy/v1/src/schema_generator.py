
from typing import List, Dict, Any

def value_schema(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs the schema for a single value using 'anyOf' to allow 'None'.
    """
    NONE = {"type": "string", "enum": ["None"]}
    
    field_type = d.get("type", "string")
    allowed_values = d.get("allowed_values", [])
    
    if field_type == "object":
        items_type = d.get("items_type", "string")
        if items_type == "integer":
            item_schema = {"type": "integer"}
        elif items_type == "number":
            item_schema = {"type": "number"}
        elif items_type == "enum" and allowed_values:
            item_schema = {"type": "string", "enum": allowed_values}
        else:
            item_schema = {"type": "string"}
            
        return {
            "anyOf": [
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "The dynamic key, e.g., study name"},
                            "value": {
                                "type": "array",
                                "items": item_schema
                            }
                        },
                        "required": ["key", "value"]
                    }
                }, 
                NONE
            ]
        }
    
    if field_type == "integer":
        return {"anyOf": [{"type": "integer"}, NONE]}
    if field_type == "number":
        return {"anyOf": [{"type": "number"}, NONE]}
    if field_type == "number_percent":
        return {"anyOf": [{"type": "number", "minimum": 0, "maximum": 100}, NONE]}
    if field_type == "enum" or field_type == "enum_or_none": # Handle explicit enum types
        if allowed_values:
             return {"anyOf": [{"type": "string", "enum": allowed_values}, NONE]}
        return {"anyOf": [{"type": "string"}, NONE]}
        
    # Default string / unknown types
    return {"anyOf": [{"type": "string"}, NONE]}

def build_output_schema(definitions: Dict, requested_names: List[str], gender_specific_names: List[str] = None) -> Dict[str, Any]:
    """
    Builds the full JSON schema for Gemini's response_format.
    
    Args:
        definitions: The loaded JSON content from extraction_schema.json (must have "value_definitions" list)
        requested_names: List of field names to extract (e.g., ["Country", "Sample"])
        gender_specific_names: List of field names that require gender breakdowns.
    """
    if gender_specific_names is None:
        gender_specific_names = []
        
    # Convert list of dicts to name->dict map for easy lookup
    defs_by_name = {d["name"]: d for d in definitions.get("value_definitions", [])}
    
    # Define specific confidence keys (must match extraction_schema.json exactly)
    CONF_LEVEL_KEY = "Confidence Level (low, moderate, high)"
    CONF_PCT_KEY = "Confidence Percentage (scale of 0% to 100%)"
    
    # Check if user requested them
    include_conf_level = CONF_LEVEL_KEY in requested_names
    include_conf_pct = CONF_PCT_KEY in requested_names
    
    # Filter them out of the main iteration list (they are meta-properties, not standalone fields)
    main_fields = [n for n in requested_names if n not in (CONF_LEVEL_KEY, CONF_PCT_KEY)]
    
    props = {}
    required_fields = []

    for name in main_fields:
        if name not in defs_by_name:
            print(f"Warning: Definition for '{name}' not found in schema. Skipping.")
            continue
            
        d = defs_by_name[name]
        v_schema = value_schema(d)
        
        # Base properties for every field
        # Order: type, extract_value, evidence_source, warning, [confidence...]
        field_props = {
            "type": {"type": "string", "enum": [d["type"]]}, # Echo type back for sanity
            "extract_value": v_schema,
            "evidence_source": {"type": "string"},
            "warning": {"type": "string"}
        }
        field_req = ["type", "extract_value", "evidence_source", "warning"]
        
        # Conditionally add confidence
        if include_conf_level:
            field_props["confidence_level"] = {"type": "string", "enum": ["low", "moderate", "high"]}
            field_req.append("confidence_level")
            
        if include_conf_pct:
            field_props["confidence_pct"] = {"type": "integer"}
            field_req.append("confidence_pct")

        # Add Gender Specific Logic
        if name in gender_specific_names:
            field_props["extract_value_by_gender"] = {
              "type": "object",
              "properties": {
                "female": v_schema,
                "male": v_schema,
                "other": v_schema,
                "total": v_schema,
              },
              "required": ["female", "male", "other", "total"]
            }
            field_req.append("extract_value_by_gender")

        props[name] = {
          "type": "object",
          "properties": field_props,
          "required": field_req
        }
        required_fields.append(name)
        
    return {
      "type": "object",
      "properties": props,
      "required": required_fields
    }
