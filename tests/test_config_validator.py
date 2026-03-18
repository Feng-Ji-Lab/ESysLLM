import unittest
import os
import json
import tempfile
import shutil
import sys
sys.path.append(os.getcwd())
from src.config_validator import ConfigValidator

class TestConfigValidator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.valid_settings = {
            "api_key": "test_key",
            "model_name": "test_model",
            "requested_fields": ["Field1"],
            "gender_specific_fields": [],
            "papers_json_path": self.test_dir
        }
        self.valid_schema = {
            "value_definitions": [
                {"name": "Field1", "type": "string", "definition": "def"}
            ]
        }
        
        # Create a dummy paper file
        with open(os.path.join(self.test_dir, "test_paper.json"), "w") as f:
            json.dump({"content": "test"}, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_valid_settings(self):
        try:
            ConfigValidator.validate_settings(self.valid_settings)
        except ValueError as e:
            self.fail(f"validate_settings raised ValueError unexpectedly: {e}")

    def test_missing_key(self):
        settings = self.valid_settings.copy()
        del settings["api_key"]
        with self.assertRaises(ValueError):
            ConfigValidator.validate_settings(settings)

    def test_empty_value(self):
        settings = self.valid_settings.copy()
        settings["api_key"] = ""
        with self.assertRaises(ValueError):
            ConfigValidator.validate_settings(settings)

    def test_non_existent_path(self):
        settings = self.valid_settings.copy()
        settings["papers_json_path"] = "non_existent_path_12345"
        with self.assertRaises(FileNotFoundError):
            ConfigValidator.validate_settings(settings)

    def test_valid_schema(self):
        try:
            ConfigValidator.validate_extraction_schema(self.valid_schema, ["Field1"])
        except ValueError as e:
            self.fail(f"validate_extraction_schema raised ValueError: {e}")

    def test_missing_field_in_schema(self):
        with self.assertRaisesRegex(ValueError, "Requested fields not found"):
            ConfigValidator.validate_extraction_schema(self.valid_schema, ["Field2"])

    def test_invalid_enum(self):
        schema = {
            "value_definitions": [
                {"name": "Field1", "type": "enum_or_none", "definition": "def"}
                # Missing allowed_values
            ]
        }
        with self.assertRaisesRegex(ValueError, "missing 'allowed_values'"):
            ConfigValidator.validate_extraction_schema(schema, ["Field1"])

    def test_valid_input_files(self):
        # Create a valid paper folder structure
        paper_folder = os.path.join(self.test_dir, "valid_paper")
        os.makedirs(paper_folder)
        with open(os.path.join(paper_folder, "valid_paper.json"), "w") as f:
            json.dump({"content": "test"}, f)
            
        try:
            ConfigValidator.validate_input_files(self.test_dir)
        except Exception as e:
            self.fail(f"validate_input_files failed: {e}")

    def test_missing_json_in_subfolder(self):
        # Create a paper folder WITHOUT the expected JSON
        paper_folder = os.path.join(self.test_dir, "broken_paper")
        os.makedirs(paper_folder)
        # Empty folder or wrong file name
        with open(os.path.join(paper_folder, "wrong_name.json"), "w") as f:
            json.dump({}, f)

        with self.assertRaisesRegex(ValueError, "missing expected JSON file"):
            ConfigValidator.validate_input_files(self.test_dir)
            
    def test_invalid_json_content(self):
        # Create a paper folder with BROKEN JSON
        paper_folder = os.path.join(self.test_dir, "bad_json_paper")
        os.makedirs(paper_folder)
        with open(os.path.join(paper_folder, "bad_json_paper.json"), "w") as f:
            f.write("{broken")

        with self.assertRaisesRegex(ValueError, "Invalid JSON"):
            ConfigValidator.validate_input_files(self.test_dir)

    def test_real_repo_data(self):
        """Test validation against the actual repo files to ensure they are compliant."""
        # Assumption: running from project root
        base_dir = os.getcwd() 
        config_dir = os.path.join(base_dir, "config")
        test_papers_dir = os.path.join(base_dir, "test", "papers")
        
        schema_path = os.path.join(config_dir, "extraction_schema.json")
        settings_path = os.path.join(config_dir, "settings.json")
        
        if not os.path.exists(schema_path) or not os.path.exists(settings_path):
             # Skip if not running in expected environment
             print("Skipping real repo test: config files not found.")
             return

        # Load real settings to get requested fields
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            
        requested_fields = settings.get("requested_fields", [])
        
        # Load real schema
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
            
        # Validate Schema
        try:
            ConfigValidator.validate_extraction_schema(schema, requested_fields)
        except Exception as e:
            self.fail(f"Real extraction_schema.json failed validation: {e}")
            
        # Validate Papers
        if os.path.exists(test_papers_dir):
            try:
                ConfigValidator.validate_input_files(test_papers_dir)
            except Exception as e:
                self.fail(f"Real test/papers directory failed validation: {e}")
        else:
            print(f"Skipping real papers test: {test_papers_dir} not found.")

if __name__ == '__main__':
    unittest.main()