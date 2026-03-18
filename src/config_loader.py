import json
import os
from typing import Dict, Any
from src.config_validator import ConfigValidator

class ConfigLoader:
    def __init__(self, base_dir: str = None):
        # Fallback to project root if base_dir is invalid or not provided
        if base_dir is None or not os.path.isdir(base_dir):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir
        self.settings_path = os.path.join(base_dir, "config", "settings.json")
        self.extraction_schema_path = os.path.join(base_dir, "config", "extraction_schema.json")
        self.sys_prompt_path = os.path.join(base_dir, "config", "system_prompt_template.json")
        self.user_prompt_path = os.path.join(base_dir, "config", "user_prompt_template.json")
        self.aggregation_prompt_path = os.path.join(base_dir, "config", "aggregation_prompt_template.json")
        
        # Load immediately
        self.settings = self._load_json(self.settings_path)
        self.extraction_schema = self._load_json(self.extraction_schema_path)
        self.system_prompt_template = self._load_json(self.sys_prompt_path)
        self.user_prompt_template = self._load_json(self.user_prompt_path)
        self.aggregation_prompt_template = self._load_json(self.aggregation_prompt_path)
        
        self.table_rules_path = os.path.join(base_dir, "config", "table_rules.txt")
        self.table_rules_content = self._load_text(self.table_rules_path)

        # Validate
        self._validate()

    def _validate(self):
        """Run strict validation on loaded settings and schema."""
        print("Validating configuration...")
        ConfigValidator.validate_settings(self.settings)
        ConfigValidator.validate_extraction_schema(self.extraction_schema, self.requested_fields)
        ConfigValidator.validate_input_files(self.papers_json_path)
        print("Configuration valid.")

    def _load_json(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_text(self, path: str) -> str:
        if not os.path.exists(path):
             return ""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    @property
    def api_key(self) -> str:
        return self.settings.get("api_key", "")

    @property
    def model_name(self) -> str:
        return self.settings.get("model_name", "gemini-1.5-pro-002")

    @property
    def papers_json_path(self) -> str:
        return self.settings.get("papers_json_path", "")

    @property
    def requested_fields(self) -> list:
        return self.settings.get("requested_fields", [])
        
    @property
    def gender_fields(self) -> list:
        return self.settings.get("gender_specific_fields", [])
        
    @property
    def table_rules(self) -> str:
        return self.table_rules_content

    @property
    def property_definitions(self) -> Dict[str, str]:
        """Returns the property definitions from system prompt template."""
        return self.system_prompt_template.get("property_definitions", {})

    @property
    def gender_difference_policy(self) -> Dict[str, Any]:
        """Returns the gender difference policy from system prompt template."""
        return self.system_prompt_template.get("gender_difference_policy", {})
