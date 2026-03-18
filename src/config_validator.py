import os
import json
from typing import Dict, Any, List

class ConfigValidator:
    REQUIRED_SETTINGS = [
        "api_key",
        "model_name",
        "requested_fields",
        "gender_specific_fields",
        "papers_json_path"
    ]

    REQUIRED_FIELD_KEYS = ["name", "type", "definition"]
    ENUM_TYPE = "enum_or_none"
    ENUM_KEYS = ["allowed_values"]

    @staticmethod
    def validate_settings(settings: Dict[str, Any]) -> None:
        """
        Validates the settings dictionary for required keys and non-empty values.
        Raises ValueError if validation fails.
        """
        missing_keys = [key for key in ConfigValidator.REQUIRED_SETTINGS if key not in settings]
        if missing_keys:
            raise ValueError(f"Settings missing required keys: {', '.join(missing_keys)}")

        # Check for empty values
        for key in ConfigValidator.REQUIRED_SETTINGS:
            val = settings.get(key)
            if not val and not isinstance(val, (list, bool, int, float)): # Allow empty list if intentional, but warn? 
                # strictly api_key and model_name should be strings
                if key in ["api_key", "model_name", "papers_json_path"]:
                    if not val or not isinstance(val, str) or not val.strip():
                        raise ValueError(f"Settings value for '{key}' must be a non-empty string.")

        # Validate papers_json_path existence
        path = settings["papers_json_path"]
        if not os.path.exists(path):
            raise FileNotFoundError(f"papers_json_path does not exist: {path}")
        
    @staticmethod
    def validate_extraction_schema(schema: Dict[str, Any], requested_fields: List[str]) -> None:
        """
        Validates the extraction schema against the requested fields.
        1. requested_fields must exist in schema.
        2. Schema definitions must be valid.
        """
        if "value_definitions" not in schema:
            raise ValueError("Extraction schema missing 'value_definitions' key.")

        defs = {d["name"]: d for d in schema["value_definitions"]}
        
        # 1. Check requested fields exist
        missing_fields = [f for f in requested_fields if f not in defs]
        if missing_fields:
            raise ValueError(f"Requested fields not found in extraction schema: {', '.join(missing_fields)}")

        # 2. Validate schema structure strictly for requested fields
        for field_name in requested_fields:
            field_def = defs[field_name]
            
            # Check required keys
            for req in ConfigValidator.REQUIRED_FIELD_KEYS:
                if req not in field_def:
                    raise ValueError(f"Field '{field_name}' in schema is missing required key '{req}'.")

            # Check enum constraints
            if field_def["type"] == ConfigValidator.ENUM_TYPE:
                if "allowed_values" not in field_def:
                     raise ValueError(f"Field '{field_name}' has type '{ConfigValidator.ENUM_TYPE}' but missing 'allowed_values'.")
                if not isinstance(field_def["allowed_values"], list) or not field_def["allowed_values"]:
                     raise ValueError(f"Field '{field_name}' 'allowed_values' must be a non-empty list.")

    @staticmethod
    def validate_input_files(papers_path: str) -> None:
        """
        Validates that papers_json_path contains valid inputs.
        Ensures every paper subfolder contains one valid JSON file.
        
        Logic:
        1. Iterate all items in papers_path.
        2. If item is a directory, it is treated as a paper folder.
        3. It MUST contain a file named "{folder_name}.json".
        4. That file MUST be valid JSON.
        """
        if not os.path.exists(papers_path):
            raise FileNotFoundError(f"Input path not found: {papers_path}")

        items = os.listdir(papers_path)
        if not items:
            print(f"Warning: Input path '{papers_path}' is empty.")
            return

        errors = []
        paper_folders_found = 0

        for item in items:
            item_path = os.path.join(papers_path, item)
            
            # We focus on Directories as "Papers"
            if os.path.isdir(item_path):
                paper_folders_found += 1
                expected_json_name = f"{item}.json"
                expected_json_path = os.path.join(item_path, expected_json_name)
                
                if not os.path.exists(expected_json_path):
                    errors.append(f"Paper folder '{item}' is missing expected JSON file: {expected_json_name}")
                    continue
                
                # Check for valid JSON content
                try:
                    with open(expected_json_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    errors.append(f"Invalid JSON in {expected_json_path}: {e}")
                except Exception as e:
                     errors.append(f"Error reading {expected_json_path}: {e}")

        if paper_folders_found == 0:
             # Warn if no valid paper folders are found
             pass

        if errors:
            raise ValueError(f"Validation failed for input papers:\n" + "\n".join(errors))
