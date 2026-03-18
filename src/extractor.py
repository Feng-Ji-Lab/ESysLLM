import json
import time
import os
import copy
from typing import Dict, Any, List, Optional
from src.api_client import APIClient

from src.config_loader import ConfigLoader
from src.schema_generator import build_output_schema

class MetaAnalysisExtractor:
    def __init__(self, config: ConfigLoader):
        self.config = config
        self.api_client = APIClient(config)
        
        # Pre-build schema based on configuration
        self.output_schema = build_output_schema(
            self.config.extraction_schema,
            self.config.requested_fields,
            self.config.gender_fields
        )

    def extract_section(self, section_text: str, assets: List[Dict[str, str]] = None, section_context: Dict[str, str] = None) -> List[Dict[str, Any]]:
        """
        Orchestrates multi-pass extraction:
        1. Text-Only Pass (No table rules)
        2. Per-Asset Pass (One per figure/table, with table rules)
        
        Args:
            section_text: Main text content.
            assets: List of dicts with keys {'path', 'type', 'caption'}.
            section_context: Context for prompt replacement (section_id, section_title).
        
        Returns:
            List of result dictionaries from all passes.
        """
        if assets is None:
            assets = []
        if section_context is None:
            section_context = {}
            
        results = []
        
        # Pass 1: Extract from text only, excluding table rules
        print(f"    - Pass 1: Text Only ({len(section_text)} chars)")
        res_text = self._extract_pass(section_text, asset=None, context=section_context)
        if "error" not in res_text:
            res_text["_pass_type"] = "text_only"
            results.append(res_text)
        else:
            print(f"      x Error: {res_text['error']}")

        # Pass 2..N: Extract from individual assets including table rules
        for i, asset in enumerate(assets):
            desc = f"[{asset['type']}] {asset.get('caption', 'No caption')}"
            print(f"    - Pass {i+2}: Asset {i+1} ({asset['type']})")
            
            res_asset = self._extract_pass(section_text, asset=asset, context=section_context)
            if "error" not in res_asset:
                res_asset["_pass_type"] = f"asset_{i}"
                res_asset["_asset_source"] = desc
                results.append(res_asset)
            else:
                print(f"      x Error: {res_asset['error']}")
                
        return results


    def _extract_pass(self, section_text: str, asset: Dict[str, str] = None, context: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Helper to execute a single LLM call.
        """
        if context is None:
            context = {}

        # 1. Prepare Dynamic Schema
        use_schema = self.output_schema
        
        # If asset exists, we want to extract 'Asset Caption'
        if asset:
            # We must rebuild schema to include 'Asset Caption'
            defs = copy.deepcopy(self.config.extraction_schema.get("value_definitions", []))
            reqs = copy.deepcopy(self.config.requested_fields)
            
            # Add definition
            defs.append({
                "name": "Asset Caption",
                "type": "string",
                "definition": "The full caption or title of the provided table or figure exactly as it appears in the text or image."
            })
            reqs.append("Asset Caption")
            
            use_schema = build_output_schema(
                {"value_definitions": defs},
                reqs,
                self.config.gender_fields
            )

        # 2. Prepare System Prompt
        sys_template = self.config.system_prompt_template
        sys_prompt_str = json.dumps(sys_template, indent=2)
        
        # Use extended definitions for the system prompt if processing an asset,
        # ensuring the model recognizes the 'Asset Caption' field.
        curr_defs = defs if asset else self.config.extraction_schema.get("value_definitions", [])
        
        definitions_str = json.dumps(curr_defs, indent=2)
        
        sys_prompt_str = sys_prompt_str.replace('"<<DEFINITIONS_JSON>>"', definitions_str)
        sys_prompt_str = sys_prompt_str.replace('"<<GENDER_FIELDS_LIST>>"', json.dumps(self.config.gender_fields)) 
        
        # 3. Prepare User Prompt
        user_template = self.config.user_prompt_template
        
        # Convert dictionary-based user template to JSON string for processing
        user_msg_content = json.dumps(user_template, indent=2)

        # Content Substitutions
        user_msg_content = user_msg_content.replace("<<SECTION_TEXT>>", section_text)
        
        # Context Replacements
        sec_id = context.get("section_id", "unknown")
        sec_title = context.get("section_title", "Unknown Section")
        user_msg_content = user_msg_content.replace("<<SECTION_ID>>", sec_id)
        user_msg_content = user_msg_content.replace("<<SECTION_TITLE>>", sec_title)
        
        # Extend target list if asset
        curr_reqs = reqs if asset else self.config.requested_fields
        tgt_fields_str = "\n".join([f"- {f}" for f in curr_reqs])
        
        user_msg_content = user_msg_content.replace("<<TARGET_FIELDS_LIST>>", tgt_fields_str)
        
        # Asset Handling
        attached_assets_desc = "None"
        asset_paths = []
        
        if asset:
            # Single asset mode
            original_caption = asset.get('caption', 'No caption')
            asset_type = asset.get('type', 'image')
            path = asset.get('path')
            
            attached_assets_desc = f"[{asset_type}] {original_caption}"
            if path and os.path.exists(path):
                asset_paths.append(path)
                
        user_msg_content = user_msg_content.replace("<<ATTACHED_ASSETS_LIST>>", attached_assets_desc)

        # Inject Table Rules ONLY for asset passes
        if asset:
             user_msg_content += "\n" + self.config.table_rules

        user_msg_content = user_msg_content.replace("<<ATTACHED_ASSETS_LIST>>", attached_assets_desc)

        # 4. Load asset bytes if present
        assets_for_api = []
        for path in asset_paths:
            try:
                ext = os.path.splitext(path.lower())[1]
                mime_type = "image/png" if ext == ".png" else "image/jpeg"
                with open(path, "rb") as img_f:
                    img_data = img_f.read()
                assets_for_api.append({
                    "path": path,
                    "mime_type": mime_type,
                    "data": img_data
                })
            except Exception as e:
                print(f"Warning: Failed to load asset {path}: {e}")

        # 5. Call API
        retry_count = self.config.settings.get("retry_count", 2) if hasattr(self.config, "settings") and isinstance(self.config.settings, dict) else 2
        
        res = self.api_client.generate_content(
            system_instruction=sys_prompt_str,
            user_content=user_msg_content,
            response_schema=use_schema,
            assets=assets_for_api,
            retry_count=retry_count
        )
        
        if "error" not in res:
            if asset:
                 res["_asset_link"] = asset.get('path', 'None')
                 res["_metadata_caption"] = original_caption
                 res["_asset_source"] = res.get("Asset Caption", {}).get("extract_value", original_caption)
        
        return res
