import os
import json
import time
import logging
from typing import Dict, List, Any
from src.api_client import APIClient

class Aggregator:
    def __init__(self, output_dir: str, config=None):
        self.output_dir = output_dir
        self.config = config
        self.api_client = None
        if config:
            self.api_client = APIClient(config)

    def _build_system_prompt(self, template_obj: Dict[str, Any], replacements: Dict[str, str]) -> str:
        """Helper to construct a system prompt string from a structured template object."""
        prompt_parts = []
        
        # Helper to recursively process dict/list/str
        def process_node(node, level=0):
            indent = "  " * level
            if isinstance(node, dict):
                for k, v in node.items():
                    # Format key as header if appropriate, otherwise just key-value
                    header = k.replace("_", " ").title()
                    prompt_parts.append(f"{indent}### {header}")
                    process_node(v, level + 1)
            elif isinstance(node, list):
                for item in node:
                    process_node(item, level)
            elif isinstance(node, str):
                # Apply replacements
                val = node
                for rk, rv in replacements.items():
                    val = val.replace(rk, rv)
                prompt_parts.append(f"{indent}{val}")
            else:
                 prompt_parts.append(f"{indent}{str(node)}")

        process_node(template_obj)
        return "\n\n".join(prompt_parts)


    def collect_candidates(self) -> Dict[str, Dict[int, Any]]:
        """
        Step 1: Collect all non-None candidates for each field from all sections.
        Returns a dictionary where keys are field names, and values are dictionaries 
        of candidates indexed by integers.
        """
        candidates_map = {} # { "Field Name": { 0: { ...candidate... }, 1: { ... } } }
        
        # 1. Iterate all section JSONs
        if not os.path.exists(self.output_dir):
            print(f"Error: Directory {self.output_dir} does not exist.")
            return {}

        file_list = sorted([f for f in os.listdir(self.output_dir) if f.endswith(".json") and not f.startswith("all_results")])
        
        global_index_map = {} # Track index per field
        
        for fname in file_list:
            path = os.path.join(self.output_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Error reading {fname}: {e}")
                continue

            # Handle list-of-dicts (multi-pass) vs single dict
            if isinstance(data, dict):
                passes = [data]
            else:
                passes = data
                
            for pass_data in passes:
                if not isinstance(pass_data, dict): continue
                
                pass_type = pass_data.get("_pass_type", "unknown")
                asset_link = pass_data.get("_asset_link", "None")
                meta_caption = pass_data.get("_metadata_caption", "None")
                
                # Check for LLM-extracted caption in this pass
                extracted_caption_field = pass_data.get("Asset Caption", {})
                extracted_caption = "None"
                if isinstance(extracted_caption_field, dict):
                     extracted_caption = extracted_caption_field.get("extract_value", "None")

                # Check for section summary in this pass
                section_summary = pass_data.get("section_summary", {}).get("extract_value", "None")

                # Check each field in this pass
                for field, content in pass_data.items():
                    # Skip metadata fields
                    if field.startswith("_") or field == "Asset Caption" or field == "section_summary": continue
                    
                    if not isinstance(content, dict): continue
                    
                    # Check if 'meaningful' (not None)
                    has_val = False
                    
                    # 1. Main value check
                    val = content.get("extract_value")
                    if val is not None and str(val) != "None":
                        has_val = True
                        
                    # 2. Gender split check
                    if not has_val:
                        gen_dict = content.get("extract_value_by_gender")
                        if isinstance(gen_dict, dict):
                            # Check if ANY gender value is non-None
                            for k, v in gen_dict.items():
                                if v is not None and str(v) != "None":
                                    has_val = True
                                    break
                    
                    if has_val:
                        # Prepare Candidate Block
                        candidate = content.copy()
                        candidate["source_file"] = fname
                        candidate["_pass_type"] = pass_type
                        
                        # Store detailed asset info
                        candidate["_asset_link"] = asset_link
                        candidate["_metadata_caption"] = meta_caption
                        candidate["_extracted_caption"] = extracted_caption
                        
                        # Store section summary for context
                        candidate["_section_summary"] = section_summary
                        
                        # Init field bucket if needed
                        if field not in candidates_map:
                            candidates_map[field] = {}
                            global_index_map[field] = 0
                            
                        # Add to map
                        idx = global_index_map[field]
                        candidates_map[field][idx] = candidate
                        global_index_map[field] += 1
                        
        return candidates_map

    def resolve_completeness(self, candidates_map: Dict[str, Dict[int, Any]]) -> Dict[str, Any]:
        """
        Strategy 1: Completeness-Based Prioritization.
        Returns a refined JSON with one winner per field.
        """
        final_output = {}
        
        for field, candidates in candidates_map.items():
            best_cand = None
            best_score = -1
             
            # Iterate all candidates for this field
            for idx, cand in candidates.items():
                score = 0
                
                # 1. Base Score (Found something)
                score += 1
                
                # 2. Gender Specificity Score
                gen_dict = cand.get("extract_value_by_gender")
                if isinstance(gen_dict, dict):
                    non_none_count = sum(1 for v in gen_dict.values() if v is not None and str(v) != "None")
                    score += non_none_count
                    
                # Removed Asset Boost (+0.5) per user request
                     
                if score > best_score:
                    best_score = score
                    best_cand = cand
                
            if best_cand:
                # Clean metadata for final output - remove internal keys
                keys_to_remove = ["source_file", "_pass_type", "_asset_link", "_metadata_caption", "_extracted_caption", "_asset_source"]
                clean_cand = {k: v for k, v in best_cand.items() if k not in keys_to_remove}
                final_output[field] = clean_cand
                
    def resolve_llm(self, candidates_map: Dict[str, Dict[int, Any]]) -> Dict[str, Any]:
        """
        Strategy 2: LLM-Based Resolution.
        Uses external template and dynamic schema.
        Now supports prioritized aggregation of 'Number of studies' and returns LIST values.
        """
        final_output = {}
        
        if not self.api_client or not self.config:
            print("Error: LLM Client not initialized. Pass config to Aggregator.")
            return {}

        defs = self.config.extraction_schema.get("value_definitions", [])
        
        # 1. Resolve "Number of studies" First (Context Injection)
        study_count_context = "" 
        if "Number of studies" in candidates_map:
            ns_candidates_dict = candidates_map["Number of studies"]
            ns_candidates = list(ns_candidates_dict.values())
            
            # Resolve it using Flat logic
            print("Aggregator: Resolving 'Number of studies' first for context...")
            ns_res = self._resolve_flat_field("Number of studies", ns_candidates, defs)
            
            # Extract result
            ns_val = ns_res.get("extract_value", [])
            ns_reason = ns_res.get("reason", "No reason provided")
            
            if ns_val:
                study_count_context = f"CONTEXT: The paper has {ns_val} studies. Reason: {ns_reason}"
                print(f"  -> Context set: {study_count_context}")
            
            # Store it in final output so we don't re-process it
            final_output["Number of studies"] = ns_res

        # 2. Aggregating All Fields
        study_specific_fields = self.config.settings.get("study_specific_fields", [])
        
        for field, candidates_dict in candidates_map.items():
            if field == "section_summary": continue
            if field == "Number of studies": continue # Already processed
            
            # Convert dict {0: cand, 1: cand} to list [cand, cand]
            candidates = list(candidates_dict.values())

            # Check if this field should be Study-Specific (Dict) or Flat (List)
            if field in study_specific_fields:
                # Use existing logic for Study Resolution (Expects Dict)
                res = self._resolve_single_field(field, candidates_dict, defs, context_str=study_count_context)
                final_output[field] = res
            else:
                # Use new logic for Flat Fields (Expects List)
                # Pass context to flat fields too if needed? Currently _resolve_flat_field doesn't take context_str.
                # Let's update _resolve_flat_field signature to accept context_str
                res = self._resolve_flat_field(field, candidates, defs, context_str=study_count_context)
                final_output[field] = res
            
        # --- Final Consistency Check (User Request) ---
        """
        Check if 'Sample' indicates a single-gender study (only one gender has non-zero values).
        If so, propagate 'total' values to that gender for other fields if that gender's list is empty.
        """
        sample_data = final_output.get("Sample", {})
        gender_data = sample_data.get("extract_value_by_gender", {})
        
        if isinstance(gender_data, dict):
            # Iterate through all available genders ("male", "female", etc.)
            # But the structure is now: gender_data["male"] = {"Study 1": [...]}
            
            # We need to find the set of ALL Studies first
            all_studies = set()
            for g in ["male", "female", "other", "total"]:
                study_map = gender_data.get(g, {})
                if isinstance(study_map, dict):
                    all_studies.update(study_map.keys())
            
            for study in all_studies:
                # Check active genders FOR THIS STUDY
                has_male = False
                male_vals = gender_data.get("male", {}).get(study, [])
                if male_vals and any(v is not None and str(v) != "None" and float(v) > 0 for v in male_vals if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit()):
                   has_male = True
                   
                has_female = False
                female_vals = gender_data.get("female", {}).get(study, [])
                if female_vals and any(v is not None and str(v) != "None" and float(v) > 0 for v in female_vals if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit()):
                   has_female = True

                target_gender = None
                if has_male and not has_female: target_gender = "male"
                elif has_female and not has_male: target_gender = "female"
                
                if target_gender:
                    print(f"Aggregator: Detected Single Gender Study ({target_gender}) for {study}. Ensuring consistency...")
                    
                    # Fix other fields FOR THIS STUDY
                    for field, data in final_output.items():
                        if "extract_value_by_gender" in data:
                            g_dict = data["extract_value_by_gender"] # { "male": {"Study 1": ...} }
                            if not isinstance(g_dict, dict): continue
                            
                            # Get lists for this study
                            t_val = g_dict.get("total", {})
                            if not isinstance(t_val, dict):
                                print(f"DEBUG: Field {field} 'total' is not dict! It is {type(t_val)}: {t_val}")
                                continue
                            
                            tg_val = g_dict.get(target_gender, {})
                            if not isinstance(tg_val, dict):
                                print(f"DEBUG: Field {field} '{target_gender}' is not dict! It is {type(tg_val)}: {tg_val}")
                                continue

                            total_list = t_val.get(study, [])
                            target_list = tg_val.get(study, [])
                            
                            # If 'total' is missing but 'extract_value' exists, propagate main extraction to 'total'
                            main_val_map = data.get("extract_value", {})
                            main_vals = main_val_map.get(study, []) if isinstance(main_val_map, dict) else []

                            if (len(total_list) == 0) and (len(main_vals) > 0):
                                # Copy Main -> Total
                                if "total" not in g_dict: g_dict["total"] = {}
                                g_dict["total"][study] = main_vals
                                total_list = main_vals
                                print(f"  - Copied {field} Main -> Total for {study}")
                            
                            # If target gender list is empty, but total has data -> Copy Total
                            if (len(target_list) == 0) and (len(total_list) > 0):
                                if target_gender not in g_dict: g_dict[target_gender] = {}
                                g_dict[target_gender][study] = total_list
                                print(f"  - Copied {field} Total -> {target_gender} for {study}")
                             
        return final_output

    def _resolve_single_field(self, field: str, candidates: Dict[int, Any], defs: List[Dict], context_str: str) -> Dict[str, Any]:
        """Helper to resolve a single field using LLM with DICTIONARY schema."""
        
        tpl = self.config.aggregation_prompt_template.get("study_specific_prompt", {})
        
        # 1. Find Field Definition
        field_def_obj = next((d for d in defs if d["name"] == field), None)
        field_def_str = json.dumps(field_def_obj, indent=2) if field_def_obj else "No definition found."
        field_type_internal = field_def_obj["type"] if field_def_obj else "string"
        items_type_internal = field_def_obj.get("items_type", "string") if field_def_obj else "string"
        allowed_values = field_def_obj.get("allowed_values", []) if field_def_obj else []
        
        # 2. Build Dynamic Output Schema (DICTIONARY BASED)
        # We need a dictionary where keys are Study Names and values are Lists.
        # However, JSON schema for dynamic keys is tricky with Gemini "response_schema".
        # Better approach: 
        # Return an object with fixed structure:
        # { 
        #   "resolved_studies": [ 
        #       { "study_name": "Study 1", "extract_value": [...], "extract_value_by_gender": {...} },
        #       { "study_name": "Study 2", ... } 
        #   ] 
        # }
        # Then transforms back to User's desired Dictionary format in Python.
        
        if field_type_internal == "object":
            gemini_type = self._map_to_gemini_type(items_type_internal)
        else:
            gemini_type = self._map_to_gemini_type(field_type_internal)
        
        # Inner Value Schema (List of Values)
        value_schema = {
            "type": "ARRAY",
            "items": {"type": gemini_type}
        }
        
        if allowed_values and (items_type_internal == "enum" or field_type_internal == "enum"):
            value_schema["items"]["type"] = "STRING"
            value_schema["items"]["enum"] = allowed_values
        
        # Handle special case: number_or_object (Correlation) -> allow STRING to capture JSON/Object
        if field_type_internal == "number_or_object":
             value_schema["items"]["type"] = "STRING"

        # Get gender specific fields from config
        gender_fields = self.config.settings.get("gender_specific_fields", [])
        is_gender_specific = (field in gender_fields)

        study_block_schema = {
            "type": "OBJECT",
            "properties": {
                "study_name": {"type": "STRING", "description": "Name of the study (e.g., 'Study 1', 'Experiment 2')."},
                "extract_value": value_schema
            },
            "required": ["study_name", "extract_value"]
        }

        if is_gender_specific:
            print(f"Aggregator: Field {field} is gender specific.")
            study_block_schema["properties"]["extract_value_by_gender"] = {
                "type": "OBJECT",
                "properties": {
                    "male": value_schema,
                    "female": value_schema,
                    "other": value_schema,
                    "total": value_schema
                }
            }
            study_block_schema["required"].append("extract_value_by_gender")

        resolution_schema = {
            "type": "OBJECT",
            "properties": {
                "resolved_studies": {
                    "type": "ARRAY",
                    "items": study_block_schema
                },
                "best_indices": {
                    "type": "ARRAY", 
                    "items": {"type": "INTEGER"},
                    "description": "List of candidate indices used."
                },
                "reason": {
                    "type": "STRING",
                    "description": "Reasoning for selection/merging and study resolution."
                }
            },
            "required": ["resolved_studies", "best_indices", "reason"]
        }

        # 3. Construct Prompts (Structured)
        # Prepare replacements
        replacements = {
            "<<FIELD_NAME>>": field,
            "<<FIELD_DEFINITION>>": field_def_str
        }
        
        # Build System Prompt from Structured Dict
        sys_prompt_obj = tpl.get("system_prompt", {})
        if isinstance(sys_prompt_obj, str):
            # Fallback if somehow still string
            sys_prompt = sys_prompt_obj
            for k, v in replacements.items():
                 sys_prompt = sys_prompt.replace(k, v)
        else:
            # New structured builder
            sys_prompt = self._build_system_prompt(sys_prompt_obj, replacements)
        
        # Inject Context into System Prompt if available (e.g. Total Study Count)
        if context_str:
            sys_prompt += f"\n\n### Context\n{context_str}"

        
        cand_str = ""
        for idx, cand in candidates.items():
            val = cand.get("extract_value", "None")
            gen_val = cand.get("extract_value_by_gender", "None")
            evid = cand.get("evidence_source", "None")
            src = cand.get("source_file", "unknown")
            ptype = cand.get("_pass_type", "unknown")
            
            # Enhanced Source Info with Asset/Caption/Summary
            asset_link = cand.get("_asset_link", "None")
            meta_cap = cand.get("_metadata_caption", "None")
            ext_cap = cand.get("_extracted_caption", "None")
            sect_sum = cand.get("_section_summary", "None")
            
            source_desc = f"{src} ({ptype})"
            if asset_link != "None":
                cap_to_use = ext_cap if ext_cap != "None" else meta_cap
                source_desc += f" [Asset: {asset_link}] [Caption: {cap_to_use}]"
            
            cand_str += f"[{idx}] Source: {source_desc}\n    Value: {val}\n    Gender: {gen_val}\n    Evidence: {evid}\n    Section Summary: {sect_sum}\n\n"
            
        user_msg = tpl["user_prompt"]
        user_msg = user_msg.replace("<<FIELD_NAME>>", field)
        user_msg = user_msg.replace("<<CANDIDATES_LIST>>", cand_str)

        retry_count = self.config.settings.get("retry_count", 2) if self.config and hasattr(self.config, "settings") and isinstance(self.config.settings, dict) else 2
        
        llm_res = self.api_client.generate_content(
            system_instruction=sys_prompt,
            user_content=user_msg,
            response_schema=resolution_schema,
            retry_count=retry_count
        )
        
        if "error" in llm_res:
            print(f"Error resolving {field}: {llm_res['error']}")
            return {}
            
        if not isinstance(llm_res, dict):
            print(f"Warning: LLM returned non-dict for {field}: {llm_res}")
            return {}
            
        # Transform LLM list output back into the required dictionary format
        
        final_res = {
            "extract_value": {},
            "best_indices": llm_res.get("best_indices", []),
            "reason": llm_res.get("reason", "")
        }
        if is_gender_specific:
            final_res["extract_value_by_gender"] = { "male": {}, "female": {}, "other": {}, "total": {} }
        
        for study_block in llm_res.get("resolved_studies", []):
            s_name = study_block.get("study_name", "Unknown Study")
            
            # Main Value
            final_res["extract_value"][s_name] = study_block.get("extract_value", [])
            
            # Gender Values
            if is_gender_specific:
                g_block = study_block.get("extract_value_by_gender", {})
                if g_block and isinstance(g_block, dict):
                    for g_key in ["male", "female", "other", "total"]:
                        val_list = g_block.get(g_key, [])
                        if not isinstance(val_list, list): val_list = [val_list] if val_list is not None else []
                        final_res["extract_value_by_gender"][g_key][s_name] = val_list
        
        return final_res

    def _resolve_flat_field(self, field: str, candidates: list, defs: list, context_str: str = "") -> dict:
        """
        Aggregates a field that should be a simple list (not study-keyed dictionary).
        Example: Author, Year, Publication type.
        """
        # Find definition
        f_def = next((d for d in defs if d["name"] == field), {})
        f_desc = json.dumps(f_def, indent=2) if f_def else "No definition found."
        field_type_internal = f_def.get("type", "string")

        # Construct Prompt using Template
        tpl = self.config.aggregation_prompt_template.get("flat_prompt", {})
        sys_prompt_obj = tpl.get("system_prompt", {})
        
        replacements = {
            "<<FIELD_NAME>>": field,
            "<<FIELD_DEFINITION>>": f_desc
        }

        if isinstance(sys_prompt_obj, str):
             sys_prompt = sys_prompt_obj
             for k, v in replacements.items():
                 sys_prompt = sys_prompt.replace(k, v)
        else:
             sys_prompt = self._build_system_prompt(sys_prompt_obj, replacements)
        
        if context_str:
            sys_prompt += f"\n\n### Context\n{context_str}"

        cand_str = ""
        for i, c in enumerate(candidates):
            val = c.get("extract_value", [])
            evidence = c.get("evidence", "No evidence")
            sec_sum = c.get("_section_summary", "")
            cand_str += f"Candidate [{i}]: Value={val} | Evidence={evidence} | Section Context: {sec_sum}\n"

        user_template = tpl.get("user_prompt", "")
        user_content = user_template.replace("<<CANDIDATES_LIST>>", cand_str)

        
        # Define Schema for Flat Fields
        gemini_type = self._map_to_gemini_type(field_type_internal)
        
        flat_resolution_schema = {
            "type": "OBJECT",
            "properties": {
                "extract_value": {
                    "type": "ARRAY",
                    "items": {"type": gemini_type}
                },
                "best_indices": {
                    "type": "ARRAY", 
                    "items": {"type": "INTEGER"},
                    "description": "List of candidate indices used."
                },
                "reason": {
                    "type": "STRING",
                    "description": "Reasoning for selection."
                }
            },
            "required": ["extract_value", "best_indices", "reason"]
        }

        retry_count = self.config.settings.get("retry_count", 2) if self.config and hasattr(self.config, "settings") and isinstance(self.config.settings, dict) else 2
        
        llm_res = self.api_client.generate_content(
            system_instruction=sys_prompt,
            user_content=user_content,
            response_schema=flat_resolution_schema,
            retry_count=retry_count
        )
        
        if "error" in llm_res:
            print(f"LLM Aggregation failed for {field} (Flat): {llm_res['error']}")
            return {"extract_value": [], "best_indices": [], "reason": f"LLM Error: {llm_res['error']}"}
            
        if not isinstance(llm_res, dict):
             print(f"Warning: LLM returned non-dict for {field} (Flat): {llm_res}")
             return {"extract_value": [], "best_indices": [], "reason": f"LLM returned {type(llm_res)}"}
             
        return llm_res

    def _map_to_gemini_type(self, internal_type: str) -> str:
        if "integer" in internal_type: return "INTEGER"
        if "number" in internal_type: return "NUMBER"
        return "STRING"
