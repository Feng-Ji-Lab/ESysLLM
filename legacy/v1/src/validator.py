import json
import os
import re
from typing import Dict, Any, Tuple, List

class Validator:
    def __init__(self, ground_truth_path: str, code_book_path: str = "config/code_book.json", threshold: float = 0.05, target_fields: List[str] = None):
        # Allow passing .json directly, or swap .xlsx to .json
        if ground_truth_path.endswith(".json"):
             self.ground_truth_path = ground_truth_path
        else:
             self.ground_truth_path = ground_truth_path.replace(".xlsx", ".json")
             
        self.gt_data = self._load_json(self.ground_truth_path)
        
        # Load Code Book
        self.code_book = self._load_json(code_book_path)
        self.country_map = self.code_book.get("Country", {})
        self.enum_map = self.code_book.get("ENUM_MAPPING", {})
        
        self.threshold = threshold
        self.target_fields = target_fields if target_fields else []
        
        # Mapping from GT Key -> Extracted Field Key
        self.key_mapping = {
            "Survey method (paper-and-pencil, online)": "Survey method",
            "Source of sample (community, college, primary/secondary/ high school)": "Source of sample",
            "Assessment of BMI (self-reported or measured)": "Assessment of BMI",
            "Publication type (Journal or Dissertation)": "Publication type",
            "Assessment of BA": "Assessment of BA",
            "Country": "Country"
        }

    def _load_json(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
             # Try relative to project root if not found
             project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
             if os.path.exists(os.path.join(project_root, path)):
                 path = os.path.join(project_root, path)
             elif os.path.exists(os.path.join(os.getcwd(), path)):
                 path = os.path.join(os.getcwd(), path)
             else:
                 print(f"Warning: File not found: {path}")
                 return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return {}

    def get_ground_truth_for_paper(self, filename: str) -> Dict[str, Any]:
        clean_name = os.path.splitext(filename)[0]
        # Direct Match
        if clean_name in self.gt_data: return self.gt_data[clean_name]
        # Partial Match (GT key matches start of filename)
        for gt_name, data in self.gt_data.items():
            if clean_name.startswith(gt_name): return data
        return {}

    def _flatten_values(self, raw_data: Any) -> List[Any]:
        """Flatten extracted data (which might be Dict[Study, List[Val]] or List[Val]) to a single List[Val]."""
        vals = []
        if isinstance(raw_data, dict):
            for sub_list in raw_data.values():
                if isinstance(sub_list, list):
                    vals.extend(sub_list)
                else:
                    vals.append(sub_list)
        elif isinstance(raw_data, list):
             vals = raw_data
        else:
             vals = [raw_data]
        return vals

    def _normalize_extracted(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Organize extracted values for comparison. 
        Flattens the multi-study dictionary structure into single lists for validation.
        """
        organized = {}
        
        for field, info in extracted_data.items():
            if "extract_value" not in info and "extract_value_by_gender" not in info:
                continue

            # Check if this is an Enum/Country field
            is_enum = False
            field_enum_map = None
            if field == "Country":
                 is_enum = True
            elif field in self.enum_map:
                 is_enum = True
                 field_enum_map = self.enum_map[field]
            
            # --- Field Structure Handling ---

            # 1. Enum / Scalar Fields (Prioritize this check to ensure mapping happens)
            if is_enum:
                # For Enums, we usually care about the main value. 
                # Gather all values from extract_value (ignoring gender splits for enums usually)
                raw_vals = self._flatten_values(info.get("extract_value", []))
                
                codes = []
                for val in raw_vals:
                    if self._is_value_empty(val): continue
                    
                    if field == "Country":
                        # Map val to Code
                         parts = re.split(r'[,&]|\sand\s', str(val))
                         for part in parts:
                            raw = part.strip().lower()
                            c = self.country_map.get(raw)
                            if c: codes.append(c)
                    elif field_enum_map:
                         c = field_enum_map.get(str(val).lower())
                         if c is not None:
                             try: codes.append(int(c))
                             except: codes.append(c)
                         else:
                             # Keep raw if no map?
                             pass 
                organized[field] = codes
            
            # 2. Gender/Numeric Fields
            elif "extract_value_by_gender" in info:
                # Structure: { male: Dict/List, female: Dict/List, ... }
                gender_data = info["extract_value_by_gender"]
                
                organized[field] = {
                    "male": self._to_floats(self._flatten_values(gender_data.get("male", []))),
                    "female": self._to_floats(self._flatten_values(gender_data.get("female", []))),
                    "total": self._to_floats(self._flatten_values(gender_data.get("total", []))),
                    "other": self._to_floats(self._flatten_values(gender_data.get("other", [])))
                }
                
                # Fallback: if 'total' empty, check 'extract_value' root
                if not organized[field]["total"] and "extract_value" in info:
                     root_vals = self._flatten_values(info["extract_value"])
                     if root_vals:
                          organized[field]["total"] = self._to_floats(root_vals)

            # 3. Default / Other
            else:
                # Default case (Strings, Text, etc.)
                vals = self._flatten_values(info.get("extract_value", []))
                organized[field] = vals
                
        return organized

    def validate(self, extracted_raw: Dict[str, Any], ground_truth: Dict[str, Any]) -> Tuple[bool, list]:
        errors = []
        is_valid = True
        
        if not ground_truth:
             return False, ["Ground Truth is empty/missing for this paper."]

        # Organize Extracted Data (Flattened)
        organized_ext = self._normalize_extracted(extracted_raw)
        
        # Compare
        for gt_field, gt_vals in ground_truth.items():
            if gt_field in ["ID", "filename"]: continue
            
            # Resolve Extracted Field Key
            ext_field = self.key_mapping.get(gt_field, gt_field)
            
            # Filter Logic: Check if field is in target_fields
            if self.target_fields and ext_field not in self.target_fields:
                continue
            
            # Skip if GT is empty/none
            if self._is_gt_empty(gt_vals): continue
            
            # Check if Extracted has field
            if ext_field not in organized_ext:
                 errors.append(f"Field '{ext_field}' (GT: {gt_field}) Missing in Extraction")
                 is_valid = False
                 continue

            ext_vals = organized_ext[ext_field]
            
            # Comparison Logic: partial/full match logic from build_dashboard.py
            # If ANY match found -> Pass.
            
            # Case A: Dictionary (Gender Split)
            if isinstance(gt_vals, dict) and "male" in gt_vals:
                # Handle Mismatch: GT is Dict, Ext is List/Dict
                if not isinstance(ext_vals, dict):
                    # Should be dict due to _normalize_extracted logic for gender fields
                    if isinstance(ext_vals, list):
                         ext_vals = { "male": [], "female": [], "total": ext_vals }
                    else:
                         pass
                
                # Check for Dictionary-based GT where keys are study names/IDs
                # We essentially flatten GT side too for looser validation
                normalized_gt = {
                    "male": self._flatten_values(gt_vals.get("male", [])),
                    "female": self._flatten_values(gt_vals.get("female", [])),
                    "total": self._flatten_values(gt_vals.get("total", [])),
                    "other": self._flatten_values(gt_vals.get("other", []))
                }

                # Iterate genders
                for gender in ["male", "female", "total"]:
                    gt_g_list = normalized_gt.get(gender, [])
                    if self._is_gt_empty(gt_g_list): continue # Skip empty GT gender

                    # Flatten GT List (ensure scalar list)
                    gt_scalars = self._flatten_to_scalars(gt_g_list)
                    
                    ext_g_list = ext_vals.get(gender, [])
                    
                    # VALIDATION: Check if GT values are a SUBSET of Extracted (Partial Match is OK)
                    # Or overlap? User said "fully match and partial match are all considered as pass".
                    # Usually "partial match" means SOME items match. "Subset" means ALL GT items found.
                    # build_dashboard.py uses:
                    # - Full: Equal multisets
                    # - Partial: GT is subset of Ext (values_subset)
                    
                    # We will use values_subset logic (Pass if GT is subset of Ext)
                    if not self._values_subset(gt_scalars, ext_g_list):
                         errors.append(f"{ext_field} ({gender}): GT values {gt_scalars} NOT FULLY FOUND in Extracted {ext_g_list}")
                         is_valid = False

            # Case B: List (Enum/Scalar)
            else:
                # GT is List of codes/scalars or Dict {study: [val]}
                gt_scalars = self._flatten_to_scalars(gt_vals)
                
                # Ext is List of codes/scalars (already flattened)
                if not isinstance(ext_vals, list): ext_vals = [ext_vals]
                
                if not self._values_subset(gt_scalars, ext_vals):
                    errors.append(f"{ext_field}: GT values {gt_scalars} NOT FULLY FOUND in Extracted {ext_vals}")
                    is_valid = False
            
        return is_valid, errors

    def _flatten_to_scalars(self, val) -> List[Any]:
        """Flatten arbitrary GT structure (Dict/List) to list of scalar values."""
        if isinstance(val, dict):
             # Recursively flatten values
             res = []
             for v in val.values():
                 res.extend(self._flatten_to_scalars(v))
             return res
        elif isinstance(val, list):
             res = []
             for v in val:
                 res.extend(self._flatten_to_scalars(v))
             return res
        else:
             if not self._is_value_empty(val):
                 return [val]
             return []

    def _values_subset(self, gt_list: List[Any], ext_list: List[Any]) -> bool:
        """Check if every value in gt_list matches at least one value in ext_list."""
        missing = []
        
        # Working copy of ext to consume matched values (optional, strict subset?)
        # For validation we usually want Strict Subset: every GT item must be accounted for.
        ext_copy = list(ext_list)
        
        for gv in gt_list:
            found = False
            for i, ev in enumerate(ext_copy):
                if self._compare_values(gv, ev):
                    found = True
                    # Remove from ext_copy to handle duplicate values correctly (e.g. GT=[1,1], Ext=[1]) -> Fail
                    ext_copy.pop(i) 
                    break
            if not found:
                missing.append(gv)
        
        return len(missing) == 0

    def _is_gt_empty(self, val):
        if val is None: return True
        if isinstance(val, list):
            if not val: return True
            return all(self._is_gt_empty(v) for v in val)
        if isinstance(val, dict): return all(self._is_gt_empty(v) for v in val.values())
        if str(val).lower() in ["none", "nan", "."]: return True
        return False

    def _is_value_empty(self, val):
        return val is None or str(val).lower() in ["none", "nan", "."]

    def _to_floats(self, val_list):
        res = []
        for x in val_list:
            try: res.append(float(x))
            except: 
                if x is not None: res.append(x) # Keep non-numeric if float fail
        return res

    def _compare_values(self, v1, v2) -> bool:
        # v1 is GT, v2 is Extracted
        # Check for None
        if self._is_value_empty(v1) and self._is_value_empty(v2): return True
        if self._is_value_empty(v1) or self._is_value_empty(v2): return False

        if v1 == v2: return True
        
        # Numeric check
        try:
            f1 = float(v1); f2 = float(v2)
            # Use self.threshold
            if abs(f1 - f2) <= self.threshold: return True
            # Percentage scaling check (0.05 vs 5%)
            if abs(f1 * 100 - f2) <= self.threshold: return True
            if abs(f1 - f2 * 100) <= self.threshold: return True
        except:
            pass
            
        # String check
        if str(v1).lower().strip() == str(v2).lower().strip(): return True
        
        return False

