import json
import os
from src.config_loader import ConfigLoader

class UserInterface:
    def __init__(self, config: ConfigLoader):
        self.config = config

    def _safe_print(self, text):
        """Helper to print text safely regardless of console encoding."""
        try:
            print(text)
        except UnicodeEncodeError:
            # Fallback for Windows consoles with limited legacy encoding
            print(text.encode('utf-8', errors='replace').decode('utf-8', errors='replace')) # This might still fail if console can't display.
            # Better fallback:
            # print(text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
            # But sys.stdout.encoding might be None.
            pass

    def display_preview(self):
        """
        Prints the configuration preview to the console.
        Includes:
        - Resolved Schema (subset)
        - Prompts
        - Rules
        - Instructions
        """
        
        # Force UTF-8 for this method if possible, or use safe print
        import sys
        
        def p(t):
            try:
                print(t)
            except UnicodeEncodeError:
                # If printing fails, try to print safe ascii
                print(t.encode('ascii', 'replace').decode('ascii'))

        p("\n" + "="*80)
        p("                 PIPELINE CONFIGURATION PREVIEW                 ")
        p("="*80 + "\n")

        # 1. Extraction Schema Subset
        p(">>> 1. Resolved Extraction Schema (Requested Fields Only)")
        p("-" * 60)
        subset_schema = self._get_schema_subset()
        p(json.dumps(subset_schema, indent=2))
        p("\n")

        # 2. Prompts
        p(">>> 2. Extraction Prompts")
        p("-" * 60)
        p("--- System Prompt Template ---")
        p(json.dumps(self.config.system_prompt_template, indent=2))
        p("\n--- User Prompt Template ---")
        p(json.dumps(self.config.user_prompt_template, indent=2))
        p("\n")

        p("--- Property Definitions ---")
        p(json.dumps(self.config.property_definitions, indent=2))
        p("\n")

        p("--- Gender Difference Policy ---")
        p(json.dumps(self.config.gender_difference_policy, indent=2))
        p("\n")

        # 3. Table Rules
        p(">>> 3. Table Extraction Rules")
        p("-" * 60)
        p(self.config.table_rules)
        p("\n")

        # 4. Aggregation Prompt
        # 4. Aggregation Prompt
        p(">>> 4. Aggregation Prompt Template")
        p("-" * 60)
        agg_tpl = self.config.aggregation_prompt_template
        
        if isinstance(agg_tpl, dict):
            # Check for new nested structure
            if "study_specific_prompt" in agg_tpl or "flat_prompt" in agg_tpl:
                for key, section_data in agg_tpl.items():
                    if isinstance(section_data, dict):
                        p(f"\n--- {key.replace('_', ' ').title()} ---")
                        # System Prompt can be a dict (JSON) or string
                        sys_p = section_data.get("system_prompt", "N/A")
                        p(f"[System Prompt]\n{json.dumps(sys_p, indent=2) if isinstance(sys_p, dict) else sys_p}")
                        
                        user_p = section_data.get("user_prompt", "N/A")
                        p(f"\n[User Prompt]\n{json.dumps(user_p, indent=2) if isinstance(user_p, dict) else user_p}")
            else:
                # Fallback for flat structure or other keys
                p(json.dumps(agg_tpl, indent=2))
        else:
             p(str(agg_tpl))
        p("\n")
        
        # 5. Instructions
        p("="*80)
        p(" HOW TO MODIFY THIS CONFIGURATION")
        p("="*80)
        p(f"1. To change requested fields or valid values, edit:\n   {self.config.extraction_schema_path}")
        p(f"2. To change the system prompt/persona, edit:\n   {self.config.sys_prompt_path}")
        p(f"3. To change user query structure, edit:\n   {self.config.user_prompt_path}")
        p(f"4. To update specific table extraction rules, edit:\n   {self.config.table_rules_path}")
        p(f"5. To change aggregation logic prompts, edit:\n   {self.config.aggregation_prompt_path}")
        p(f"6. To change selected fields or input path, edit:\n   {self.config.settings_path}")
        p("\n")

    def _get_schema_subset(self):
        """Helper to filter schema definitions to only requested fields."""
        if not self.config.extraction_schema or "value_definitions" not in self.config.extraction_schema:
            return {}
        
        full_defs = {d["name"]: d for d in self.config.extraction_schema["value_definitions"]}
        subset = []
        
        for field in self.config.requested_fields:
            if field in full_defs:
                subset.append(full_defs[field])
        
        return {"value_definitions": subset}
