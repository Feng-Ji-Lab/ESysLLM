#!/usr/bin/env python
"""
build_dashboard.py – Generate a self-contained HTML dashboard for the
paper-extraction pipeline.

Usage:
    conda activate pytorch
    python build_dashboard.py --results_root output/test_run --out dashboard.html
    python build_dashboard.py --results_root output/test_run --ground_truth ground_truth.json --out dashboard.html
"""

import argparse
import json
import os
import re
import html
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants (mirrored 
# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

# (constants below mirror src/constants.py)  -- line repaired: the released file had
# lost the leading "#" and did not parse.
# ---------------------------------------------------------------------------
# Load constants from code_book.json
try:
    with open("config/code_book.json", "r", encoding="utf-8") as f:
        code_book = json.load(f)
    COUNTRY_TO_CONTINENT = code_book.get("Country", {})
    ENUM_MAPPING = code_book.get("ENUM_MAPPING", {})
except Exception as e:
    print(f"Warning: Could not load config/code_book.json: {e}")
    COUNTRY_TO_CONTINENT = {}
    ENUM_MAPPING = {}

# Reverse mappings: code → human-readable label (for GT display)
CONTINENT_NAMES = {1: "North America", 2: "Europe", 3: "South America",
                   4: "Asia", 5: "Africa", 6: "Oceania"}

REVERSE_ENUM = {}
for _field, _mapping in ENUM_MAPPING.items():
    REVERSE_ENUM[_field] = {v: k for k, v in _mapping.items()}

GT_KEY_MAPPING = {
    "Survey method (paper-and-pencil, online)": "Survey method",
    "Source of sample (community, college, primary/secondary/ high school)": "Source of sample",
    "Assessment of BMI (self-reported or measured)": "Assessment of BMI",
    "Publication type (Journal or Dissertation)": "Publication type",
    "Assessment of BA": "Assessment of BA",
    "Country": "Country",
}

# Fields to skip (not in ground truth, or metadata-only)
SKIP_FIELDS = {"Number of studies"}

# Fields where GT stores values as proportions (0-1) but extracted values are
# percentages (0-100).  Only values strictly between 0 and 1 are rescaled.
PERCENTAGE_FIELDS = {
    "Percent of white in participants",
    "Percentage of college or higher of participants",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_none_like(val: Any) -> bool:
    """Return True if val is a none-like placeholder."""
    if val is None:
        return True
    s = str(val).strip().lower()
    return s in ("none", "nan", "", ".")


def normalize_val(val: Any) -> Any:
    """Try to coerce val to a float; otherwise return lowered string."""
    if is_none_like(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return str(val).strip().lower()


def normalize_gt_percentage(val: float) -> float:
    """If a GT value is a proportion (between 0 exclusive and 1 inclusive),
    convert it to a percentage by multiplying by 100."""
    if isinstance(val, (int, float)) and 0 < val <= 1:
        return val * 100
    return val


def flatten_values(raw: Any) -> list:
    """Flatten dict-of-lists / list / scalar into a flat list."""
    if isinstance(raw, dict):
        vals = []
        for v in raw.values():
            if isinstance(v, list):
                vals.extend(v)
            else:
                vals.append(v)
        return vals
    if isinstance(raw, list):
        return list(raw)
    return [raw]


def get_study_buckets(raw: Any) -> List[list]:
    """Return a list of per-study value-lists from extract_value."""
    if isinstance(raw, dict):
        return [v if isinstance(v, list) else [v] for v in raw.values()]
    if isinstance(raw, list):
        return [raw]
    return [[raw]]


def norm_list(lst: list) -> list:
    """Normalize and filter nones from a list."""
    return sorted(
        [normalize_val(v) for v in lst if not is_none_like(v)],
        key=lambda x: (0, x) if isinstance(x, (int, float)) else (1, str(x)),
    )


def multiset_eq(a: list, b: list) -> bool:
    """Compare two lists as multisets (order-insensitive)."""
    na = norm_list(a)
    nb = norm_list(b)
    if len(na) != len(nb):
        return False
    for va, vb in zip(na, nb):
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            if abs(va - vb) > 0.05:
                return False
        elif va != vb:
            return False
    return True


def values_subset(gt_flat: list, ext_flat: list) -> bool:
    """Check if every GT value appears somewhere in ext_flat (partial match)."""
    gt_norm = [normalize_val(v) for v in gt_flat if not is_none_like(v)]
    ext_norm = [normalize_val(v) for v in ext_flat if not is_none_like(v)]
    if not gt_norm:
        return True
    ext_remaining = list(ext_norm)
    for gv in gt_norm:
        found = False
        for i, ev in enumerate(ext_remaining):
            if isinstance(gv, (int, float)) and isinstance(ev, (int, float)):
                if abs(gv - ev) < 0.05:
                    found = True
                    ext_remaining.pop(i)
                    break
                # percent conversion
                if abs(gv * 100 - ev) < 0.05 or abs(gv - ev * 100) < 0.05:
                    found = True
                    ext_remaining.pop(i)
                    break
            elif gv == ev:
                found = True
                ext_remaining.pop(i)
                break
        if not found:
            return False
    return True


# ---------------------------------------------------------------------------
# Enum encoding helpers (mirror validator.py logic)
# ---------------------------------------------------------------------------

def encode_country(val: Any) -> list:
    """Map a country string to continent code(s)."""
    codes = []
    parts = re.split(r'[,&]|\sand\s', str(val))
    for part in parts:
        raw = part.strip().lower()
        c = COUNTRY_TO_CONTINENT.get(raw)
        if c is not None:
            codes.append(c)
    return codes


def encode_enum(field: str, val: Any) -> Any:
    """Map an enum string value to its code."""
    mapping = ENUM_MAPPING.get(field)
    if not mapping:
        return normalize_val(val)
    code = mapping.get(str(val).strip().lower())
    if code is not None:
        return float(code)
    return normalize_val(val)


def encode_extracted_for_comparison(field: str, raw_vals: list) -> list:
    """Encode extracted values for a field to codes for GT comparison."""
    results = []
    for v in raw_vals:
        if is_none_like(v):
            continue
        if field == "Country":
            results.extend(encode_country(v))
        elif field in ENUM_MAPPING:
            enc = encode_enum(field, v)
            if enc is not None:
                results.append(enc)
        else:
            nv = normalize_val(v)
            if nv is not None:
                results.append(nv)
    return results


# ---------------------------------------------------------------------------
# Ground-truth comparison
# ---------------------------------------------------------------------------

def is_gt_val_empty(gt_val: Any) -> bool:
    """Return True if the entire GT field value is empty/none-like."""
    if gt_val is None:
        return True
    if isinstance(gt_val, list):
        return not gt_val or all(is_none_like(v) for v in gt_val)
    if isinstance(gt_val, dict):
        # Gender dict: check if all gender sub-values are empty
        if any(k in gt_val for k in ("male", "female", "total")):
            for g in ("male", "female", "total"):
                sub = gt_val.get(g, {})
                if isinstance(sub, dict):
                    vals = flatten_values(sub)
                elif isinstance(sub, list):
                    vals = sub
                else:
                    vals = [sub]
                if any(not is_none_like(v) for v in vals):
                    return False
            return True
        # Non-gender dict (e.g. {"study": [...]})
        vals = flatten_values(gt_val)
        return not vals or all(is_none_like(v) for v in vals)
    return is_none_like(gt_val)


def gt_field_has_gender(gt_val: Any) -> bool:
    """Check if a GT field value has gender sub-dicts."""
    if isinstance(gt_val, dict):
        return any(k in gt_val for k in ("male", "female", "total"))
    return False


def gt_extract_gender_lists(gt_val: dict) -> dict:
    """Extract male/female/total lists from GT dict."""
    result = {}
    for g in ("male", "female", "total"):
        sub = gt_val.get(g, {})
        if isinstance(sub, dict):
            vals = flatten_values(sub)
        elif isinstance(sub, list):
            vals = sub
        else:
            vals = [sub]
        result[g] = [v for v in vals if not is_none_like(v)]
    return result


def gt_extract_flat_list(gt_val: Any) -> list:
    """Flatten a GT value to a list (for non-gender fields)."""
    if isinstance(gt_val, dict):
        # Could be {"study": [...]} or gender dict
        if gt_field_has_gender(gt_val):
            # Flatten all genders
            vals = []
            for g in ("male", "female", "total", "other"):
                sub = gt_val.get(g, {})
                vals.extend(flatten_values(sub) if isinstance(sub, (dict, list)) else [sub])
            return [v for v in vals if not is_none_like(v)]
        else:
            return [v for v in flatten_values(gt_val) if not is_none_like(v)]
    if isinstance(gt_val, list):
        return [v for v in gt_val if not is_none_like(v)]
    return [] if is_none_like(gt_val) else [gt_val]


def compare_field(field: str, ext_data: dict, gt_val: Any) -> str:
    """
    Compare extracted field data with GT and return match status:
    'full', 'partial', or 'none'.
    """
    has_gender_gt = gt_field_has_gender(gt_val)

    # --- With gender ---
    if has_gender_gt:
        gt_genders = gt_extract_gender_lists(gt_val)
        ext_gender = ext_data.get("extract_value_by_gender", {})
        ext_val = ext_data.get("extract_value", {})

        # Fallback: if no extract_value_by_gender, try matching GT gender
        # values against flattened extract_value
        has_ext_gender = bool(ext_gender)

        # Helper: get encoded extracted values for a gender key
        def _ext_gender_encoded(g):
            ext_g_raw = ext_gender.get(g, {})
            if isinstance(ext_g_raw, dict):
                ext_g_flat = flatten_values(ext_g_raw)
            elif isinstance(ext_g_raw, list):
                ext_g_flat = ext_g_raw
            else:
                ext_g_flat = [ext_g_raw]
            return encode_extracted_for_comparison(field, ext_g_flat)

        # Determine which genders have non-empty values in GT and extracted
        is_pct = field in PERCENTAGE_FIELDS
        gt_nonempty = {}   # g -> normalized list
        ext_nonempty = {}  # g -> encoded list
        for g in ("male", "female", "total"):
            gt_g = gt_genders.get(g, [])
            gt_g_norm = [normalize_val(v) for v in gt_g if not is_none_like(v)]
            if is_pct:
                gt_g_norm = [normalize_gt_percentage(v) for v in gt_g_norm]
            if gt_g_norm:
                gt_nonempty[g] = gt_g_norm
            if has_ext_gender:
                enc = _ext_gender_encoded(g)
                if enc:
                    ext_nonempty[g] = enc

        gt_has_keys = set(gt_nonempty.keys())
        ext_has_keys = set(ext_nonempty.keys())

        # ------------------------------------------------------------------
        # Modification (2): GT only has "total" (male/female empty), and
        # extracted has no gender values at all → compare GT total vs
        # extract_value directly.
        # ------------------------------------------------------------------
        if gt_has_keys == {"total"} and (not has_ext_gender or not ext_has_keys):
            ext_flat = flatten_values(ext_val) if isinstance(ext_val, (dict, list)) else [ext_val]
            ext_encoded = encode_extracted_for_comparison(field, ext_flat)
            if multiset_eq(gt_nonempty["total"], ext_encoded):
                return "full"
            if values_subset(gt_nonempty["total"], ext_encoded):
                return "partial"
            return "none"

        # ------------------------------------------------------------------
        # Modification (1): GT has values for only one of male/female (not
        # total), and extracted has that same gender + total (the other
        # gender is empty). If the single-gender values match, that is a
        # full match — we don't penalize for GT lacking total.
        # ------------------------------------------------------------------
        gt_mf_keys = gt_has_keys - {"total"}  # non-total GT genders with values
        if has_ext_gender and len(gt_mf_keys) == 1 and "total" not in gt_has_keys:
            sole_gender = next(iter(gt_mf_keys))
            ext_enc = ext_nonempty.get(sole_gender, [])
            gt_norm = gt_nonempty[sole_gender]
            if multiset_eq(gt_norm, ext_enc):
                return "full"
            if values_subset(gt_norm, ext_enc):
                return "partial"
            return "none"

        # ------------------------------------------------------------------
        # Standard per-gender comparison
        # ------------------------------------------------------------------
        full_match = True
        partial_match = True
        all_gt_gender_vals = []

        for g in ("male", "female", "total"):
            gt_g_norm = gt_nonempty.get(g)
            if not gt_g_norm:
                continue

            all_gt_gender_vals.extend(gt_g_norm)

            if has_ext_gender:
                ext_g_encoded = ext_nonempty.get(g, [])

                if not multiset_eq(gt_g_norm, ext_g_encoded):
                    full_match = False

                if not values_subset(gt_g_norm, ext_g_encoded):
                    partial_match = False
            else:
                full_match = False

        # Fallback for partial: if no ext gender data, check flattened extract_value
        if not has_ext_gender and all_gt_gender_vals:
            ext_flat = flatten_values(ext_val) if isinstance(ext_val, (dict, list)) else [ext_val]
            ext_encoded = encode_extracted_for_comparison(field, ext_flat)
            if multiset_eq(all_gt_gender_vals, ext_encoded):
                return "full"
            if values_subset(all_gt_gender_vals, ext_encoded):
                return "partial"
            partial_match = False

        if full_match:
            return "full"
        if partial_match:
            return "partial"
        return "none"

    # --- Without gender ---
    gt_flat = gt_extract_flat_list(gt_val)
    if not gt_flat:
        return "full"  # empty GT = trivially matched

    # Get extracted values
    ext_val = ext_data.get("extract_value", [])
    ext_flat = flatten_values(ext_val) if isinstance(ext_val, (dict, list)) else [ext_val]
    ext_encoded = encode_extracted_for_comparison(field, ext_flat)

    is_pct = field in PERCENTAGE_FIELDS
    gt_norm = [normalize_val(v) for v in gt_flat if not is_none_like(v)]
    if is_pct:
        gt_norm = [normalize_gt_percentage(v) for v in gt_norm]
    if not gt_norm:
        return "full"

    # Full match: same number of buckets + multiset eq
    gt_buckets = get_study_buckets(gt_val)
    ext_buckets = get_study_buckets(ext_val)

    def _norm_gt_bucket(b):
        nl = [normalize_val(v) for v in b if not is_none_like(v)]
        if is_pct:
            nl = [normalize_gt_percentage(v) for v in nl]
        return nl

    if len(gt_buckets) == len(ext_buckets):
        # Sort bucket contents and compare as multiset of buckets
        gt_sorted = sorted([tuple(norm_list(_norm_gt_bucket(b))) for b in gt_buckets])
        ext_sorted = sorted([tuple(norm_list([normalize_val(v) for v in encode_extracted_for_comparison(field, b)])) for b in ext_buckets])
        if gt_sorted == ext_sorted:
            return "full"
        # Also try without encoding (for numeric/text fields)
        ext_sorted_raw = sorted([tuple(norm_list(b)) for b in ext_buckets])
        if gt_sorted == ext_sorted_raw:
            return "full"

    # Flat multiset comparison
    if multiset_eq(gt_norm, ext_encoded):
        return "full"

    # Partial match
    if values_subset(gt_norm, ext_encoded):
        return "partial"

    return "none"


# ---------------------------------------------------------------------------
# Paper matching
# ---------------------------------------------------------------------------

def normalize_key(s: str) -> str:
    """Normalize a string for fuzzy key matching."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def match_gt_paper(paper_id: str, gt_data: dict) -> Optional[dict]:
    """Find ground truth entry for a paper folder name."""
    if paper_id in gt_data:
        return gt_data[paper_id]
    # Clean name (strip extension if any)
    clean = os.path.splitext(paper_id)[0]
    if clean in gt_data:
        return gt_data[clean]
    # Partial match: GT key is prefix of paper_id
    for gt_key, gt_val in gt_data.items():
        if clean.startswith(gt_key):
            return gt_val
    # Normalized match
    norm_id = normalize_key(clean)
    for gt_key, gt_val in gt_data.items():
        if normalize_key(gt_key) == norm_id:
            return gt_val
    return None


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_results(results_root: str) -> Tuple[Dict[str, dict], List[str]]:
    """Load all final_results.json from paper subfolders.
    Returns (papers_data, all_fields).
    """
    papers = {}
    all_fields_set = set()
    root = Path(results_root)

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        fr = entry / "final_results.json"
        if not fr.exists():
            continue
        with open(fr, "r", encoding="utf-8") as f:
            data = json.load(f)
        papers[entry.name] = data
        for field in data:
            if field not in SKIP_FIELDS:
                all_fields_set.add(field)

    # Stable ordering: sort fields
    all_fields = sorted(all_fields_set)
    return papers, all_fields


def load_ground_truth(gt_path: str) -> dict:
    """Load ground truth JSON."""
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Build comparison data for each paper x field
# ---------------------------------------------------------------------------

# Load validation_targets from settings.json
try:
    with open("config/settings.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
    VALIDATION_TARGETS = settings.get("validation_targets", [])
except Exception as e:
    print(f"Warning: Could not load config/settings.json: {e}")
    VALIDATION_TARGETS = []

def build_comparison(papers: dict, all_fields: list, gt_data: Optional[dict]) -> dict:
    """Build a dict of {paper_id: {field: match_status}} for coloring."""
    result = {}
    if gt_data is None:
        return result

    for paper_id, paper_data in papers.items():
        gt_paper = match_gt_paper(paper_id, gt_data)
        if gt_paper is None:
            result[paper_id] = {}
            continue

        paper_matches = {}
        for gt_field, gt_val in gt_paper.items():
            if gt_field in ("ID", "filename"):
                continue
            # Map GT field name to extracted field name
            ext_field = GT_KEY_MAPPING.get(gt_field, gt_field)
            if ext_field in SKIP_FIELDS:
                continue
            
            # Filter matches by validation_targets if set
            if VALIDATION_TARGETS and ext_field not in VALIDATION_TARGETS:
                continue

            if ext_field in paper_data:
                match = compare_field(ext_field, paper_data[ext_field], gt_val)
                paper_matches[ext_field] = match
            else:
                # Field missing from extracted data — if GT is also empty,
                # treat as full match (both sides have nothing).
                if is_gt_val_empty(gt_val):
                    paper_matches[ext_field] = "full"
                else:
                    paper_matches[ext_field] = "none"

        result[paper_id] = paper_matches
    return result


def _decode_gt_val(ext_field: str, val: Any) -> str:
    """Decode a single GT coded value to a human-readable string."""
    if is_none_like(val):
        return str(val)
    if ext_field == "Country":
        try:
            code = int(float(val))
            name = CONTINENT_NAMES.get(code)
            if name:
                return f"{val} ({name})"
        except (ValueError, TypeError):
            pass
        return str(val)
    if ext_field in REVERSE_ENUM:
        try:
            code = int(float(val))
            label = REVERSE_ENUM[ext_field].get(code)
            if label:
                return f"{val} ({label})"
        except (ValueError, TypeError):
            pass
        return str(val)
    return str(val)


def build_gt_display(gt_data: Optional[dict]) -> dict:
    """Build displayable GT values for tooltips: {paper_id: {field: display_str}}."""
    if gt_data is None:
        return {}

    result = {}
    for gt_paper_id, gt_paper in gt_data.items():
        paper_display = {}
        for gt_field, gt_val in gt_paper.items():
            if gt_field in ("ID", "filename"):
                continue
            ext_field = GT_KEY_MAPPING.get(gt_field, gt_field)
            if ext_field in SKIP_FIELDS:
                continue

            if gt_field_has_gender(gt_val):
                parts = []
                for g in ("male", "female", "total"):
                    sub = gt_val.get(g, {})
                    vals = flatten_values(sub) if isinstance(sub, (dict, list)) else [sub]
                    vals = [v for v in vals if not is_none_like(v)]
                    if vals:
                        decoded = [_decode_gt_val(ext_field, v) for v in vals]
                        parts.append(f"{g}: {', '.join(decoded)}")
                paper_display[ext_field] = "; ".join(parts) if parts else "(empty)"
            else:
                vals = gt_extract_flat_list(gt_val)
                if vals:
                    decoded = [_decode_gt_val(ext_field, v) for v in vals]
                    paper_display[ext_field] = ", ".join(decoded)
                else:
                    paper_display[ext_field] = "(empty)"

        result[gt_paper_id] = paper_display
    return result


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def generate_html(papers: dict, all_fields: list, comparison: dict,
                  gt_display: dict, gt_data: Optional[dict]) -> str:
    """Generate the full self-contained HTML dashboard."""

    # Prepare JSON data blob for embedding
    dashboard_data = {
        "papers": papers,
        "fields": all_fields,
        "comparison": comparison,
        "gt_display": {},
        "gt_paper_mapping": {},
    }

    # Build GT display with proper paper mapping
    if gt_data:
        raw_gt_display = build_gt_display(gt_data)
        for paper_id in papers:
            gt_paper = match_gt_paper(paper_id, gt_data)
            if gt_paper is not None:
                # Find the GT key that matched
                for gt_key in gt_data:
                    if gt_data[gt_key] is gt_paper:
                        dashboard_data["gt_paper_mapping"][paper_id] = gt_key
                        if gt_key in raw_gt_display:
                            dashboard_data["gt_display"][paper_id] = raw_gt_display[gt_key]
                        break

    data_json = json.dumps(dashboard_data, ensure_ascii=False)

    return HTML_TEMPLATE.replace("/* __DASHBOARD_DATA__ */", data_json)


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Extraction Pipeline Dashboard</title>
<style>
:root {
  --bg: #f8f9fa;
  --text: #212529;
  --border: #dee2e6;
  --header-bg: #343a40;
  --header-text: #f8f9fa;
  --cell-border: rgba(150,150,150,0.4);
  --match-full: rgba(72, 199, 116, 0.25);
  --match-partial: rgba(255, 221, 87, 0.30);
  --match-none: rgba(255, 99, 99, 0.22);
  --match-neutral: rgba(200,200,200,0.10);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  font-size: 13px;
  background: var(--bg);
  color: var(--text);
  line-height: 1.4;
}

/* --- Controls --- */
.controls {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: #fff;
  border-bottom: 2px solid var(--border);
  padding: 10px 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.controls label { font-weight: 600; font-size: 12px; white-space: nowrap; }
.controls input[type="text"], .controls select {
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 12px;
}
.controls input[type="text"] { width: 200px; }
.controls select { max-width: 320px; }
.controls .sep { border-left: 1px solid var(--border); height: 28px; }
.controls .badge {
  background: #e9ecef;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  color: #495057;
}

/* --- Table wrapper --- */
.table-wrap {
  overflow: auto;
  max-height: calc(100vh - 60px);
  position: relative;
}

table {
  border-collapse: separate;
  border-spacing: 0;
  min-width: 100%;
}

/* --- Header --- */
thead th {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--header-bg);
  color: var(--header-text);
  padding: 8px 10px;
  font-size: 11px;
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
  border-right: 1px solid rgba(255,255,255,0.1);
  min-width: 160px;
}
thead th:first-child {
  position: sticky;
  left: 0;
  z-index: 200;
  min-width: 220px;
  max-width: 280px;
}

/* --- Body --- */
tbody td {
  vertical-align: top;
  padding: 4px 6px;
  border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border);
  min-width: 160px;
}
tbody td:first-child {
  position: sticky;
  left: 0;
  z-index: 50;
  background: #fff;
  font-weight: 600;
  font-size: 12px;
  min-width: 220px;
  max-width: 280px;
  word-break: break-word;
  border-right: 2px solid var(--border);
}

/* --- Cell block --- */
.cell-block {
  border: 1px solid var(--cell-border);
  border-radius: 4px;
  padding: 4px 6px;
  cursor: pointer;
  position: relative;
  min-height: 24px;
  transition: box-shadow 0.15s;
}
.cell-block:hover {
  box-shadow: 0 0 0 2px rgba(66,133,244,0.3);
}
.cell-block.pinned {
  box-shadow: 0 0 0 2px rgba(66,133,244,0.6);
}
.cell-block.match-full    { background: var(--match-full); }
.cell-block.match-partial { background: var(--match-partial); }
.cell-block.match-none    { background: var(--match-none); }
.cell-block.match-neutral { background: var(--match-neutral); }

/* sub-blocks */
.sub-block { margin-bottom: 3px; }
.sub-block:last-child { margin-bottom: 0; }
.sub-block-header {
  font-weight: 600;
  font-size: 11px;
  color: #495057;
}
.gender-line {
  margin-left: 12px;
  font-size: 11px;
  color: #555;
}
.gender-label { font-weight: 600; text-transform: capitalize; }
.empty-val { color: #aaa; font-style: italic; }

/* --- Tooltip --- */
.tooltip-box {
  position: fixed;
  z-index: 5000;
  background: #fff;
  border: 1px solid #aaa;
  border-radius: 6px;
  padding: 10px 12px;
  max-width: 480px;
  min-width: 200px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.18);
  font-size: 12px;
  line-height: 1.5;
  display: none;
  pointer-events: none;
  word-wrap: break-word;
}
.tooltip-box.pinned {
  pointer-events: auto;
}
.tooltip-box .tt-label { font-weight: 700; color: #333; }
.tooltip-box .tt-section { margin-top: 6px; }
.tooltip-box .tt-gt { border-top: 1px dashed #ccc; padding-top: 6px; margin-top: 6px; }

/* --- Legend --- */
.legend {
  display: flex; gap: 12px; align-items: center; font-size: 11px;
}
.legend-item {
  display: flex; align-items: center; gap: 4px;
}
.legend-swatch {
  width: 14px; height: 14px; border-radius: 3px; border: 1px solid rgba(0,0,0,0.15);
}

/* search highlight */
tr.highlight-row td:first-child { background: #fff3cd !important; }
</style>
</head>
<body>

<div class="controls" id="controls">
  <label>View:</label>
  <select id="viewMode">
    <option value="all">All papers</option>
    <option value="single">Single paper</option>
  </select>
  <select id="paperSelect" style="display:none"></select>
  <div class="sep"></div>
  <label>Search:</label>
  <input type="text" id="searchBox" placeholder="Filter papers...">
  <div class="sep"></div>
  <div class="legend">
    <div class="legend-item"><div class="legend-swatch" style="background:var(--match-full)"></div> Full match</div>
    <div class="legend-item"><div class="legend-swatch" style="background:var(--match-partial)"></div> Partial match</div>
    <div class="legend-item"><div class="legend-swatch" style="background:var(--match-none)"></div> No match</div>
    <div class="legend-item"><div class="legend-swatch" style="background:var(--match-neutral)"></div> No GT</div>
  </div>
  <div class="sep"></div>
  <span class="badge" id="paperCount"></span>
</div>

<div class="table-wrap" id="tableWrap">
  <table id="mainTable">
    <thead><tr id="headerRow"></tr></thead>
    <tbody id="tableBody"></tbody>
  </table>
</div>

<div class="tooltip-box" id="tooltip"></div>

<script>
// ---- Embedded data ----
const DATA = /* __DASHBOARD_DATA__ */;

const papers = DATA.papers;
const fields = DATA.fields;
const comparison = DATA.comparison;
const gtDisplay = DATA.gt_display;
const paperIds = Object.keys(papers).sort();

// ---- State ----
let pinnedTooltip = null;  // {paperId, field} or null

// ---- Helpers ----
function isNoneLike(v) {
  if (v === null || v === undefined) return true;
  const s = String(v).trim().toLowerCase();
  return s === 'none' || s === 'nan' || s === '' || s === '.';
}

function formatBestIndices(indices) {
  if (!indices || !indices.length) return '(none)';
  const sorted = [...indices].sort((a,b) => a - b);
  const ranges = [];
  let start = sorted[0], end = sorted[0];
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] === end + 1) {
      end = sorted[i];
    } else {
      ranges.push(start === end ? String(start) : `${start}-${end}`);
      start = end = sorted[i];
    }
  }
  ranges.push(start === end ? String(start) : `${start}-${end}`);
  return ranges.join(', ');
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function filterNoneLike(arr) {
  return (arr || []).filter(v => !isNoneLike(v));
}

function listsMatch(a, b) {
  // Compare two value lists (order-insensitive, approximate)
  if (a.length !== b.length) return false;
  const na = a.map(v => { try { return parseFloat(v); } catch(e) { return String(v).toLowerCase(); } }).sort();
  const nb = b.map(v => { try { return parseFloat(v); } catch(e) { return String(v).toLowerCase(); } }).sort();
  for (let i = 0; i < na.length; i++) {
    if (typeof na[i] === 'number' && typeof nb[i] === 'number') {
      if (Math.abs(na[i] - nb[i]) > 0.05) return false;
    } else if (String(na[i]) !== String(nb[i])) return false;
  }
  return true;
}

// ---- Cell rendering ----
function renderCell(fieldData) {
  if (!fieldData) return '<span class="empty-val">(no data)</span>';

  const ev = fieldData.extract_value;
  const evg = fieldData.extract_value_by_gender;
  let html = '';

  if (evg) {
    html = renderGenderCell(ev, evg);
  } else if (ev !== undefined) {
    html = renderPlainCell(ev);
  } else {
    html = '<span class="empty-val">(no data)</span>';
  }
  return html;
}

function renderPlainCell(ev) {
  // ev is dict or list
  if (ev && typeof ev === 'object' && !Array.isArray(ev)) {
    // Dict: per-study
    const parts = [];
    for (const [study, vals] of Object.entries(ev)) {
      const filtered = filterNoneLike(vals);
      if (filtered.length) {
        parts.push(`<div class="sub-block"><span class="sub-block-header">${esc(study)}:</span> ${filtered.map(v => esc(String(v))).join(', ')}</div>`);
      } else {
        parts.push(`<div class="sub-block"><span class="sub-block-header">${esc(study)}:</span> <span class="empty-val">(empty)</span></div>`);
      }
    }
    return parts.join('') || '<span class="empty-val">(empty)</span>';
  }
  if (Array.isArray(ev)) {
    const filtered = filterNoneLike(ev);
    if (filtered.length) {
      return `<div class="sub-block">${filtered.map(v => esc(String(v))).join(', ')}</div>`;
    }
    return '<span class="empty-val">(empty)</span>';
  }
  if (isNoneLike(ev)) return '<span class="empty-val">(empty)</span>';
  return `<div class="sub-block">${esc(String(ev))}</div>`;
}

function renderGenderCell(ev, evg) {
  // Collect all study keys from evg (from any gender dict)
  const studyKeys = new Set();
  for (const g of ['female', 'male', 'other', 'total']) {
    const gDict = evg[g];
    if (gDict && typeof gDict === 'object' && !Array.isArray(gDict)) {
      for (const k of Object.keys(gDict)) studyKeys.add(k);
    }
  }
  // Also get study keys from ev if it's a dict
  const evIsDict = (ev && typeof ev === 'object' && !Array.isArray(ev));
  if (evIsDict) {
    for (const k of Object.keys(ev)) studyKeys.add(k);
  }

  const parts = [];
  for (const study of studyKeys) {
    let headerVals = '';

    // Get extract_value for this study
    let evStudyVals = [];
    if (evIsDict && ev[study]) {
      evStudyVals = filterNoneLike(Array.isArray(ev[study]) ? ev[study] : [ev[study]]);
    }

    // Get total for this study
    let totalVals = [];
    if (evg.total && typeof evg.total === 'object' && !Array.isArray(evg.total) && evg.total[study]) {
      totalVals = filterNoneLike(Array.isArray(evg.total[study]) ? evg.total[study] : [evg.total[study]]);
    }

    // Check if total matches extract_value
    const totalMatchesEv = evStudyVals.length > 0 && totalVals.length > 0 && listsMatch(evStudyVals, totalVals);

    // Header line
    if (!totalMatchesEv && evStudyVals.length > 0) {
      headerVals = ` ${evStudyVals.map(v => esc(String(v))).join(', ')}`;
    }

    let studyHtml = `<div class="sub-block"><div class="sub-block-header">${esc(study)}:${headerVals}</div>`;

    // Gender lines
    for (const g of ['female', 'male', 'other', 'total']) {
      const gDict = evg[g];
      if (!gDict) continue;
      let gVals = [];
      if (typeof gDict === 'object' && !Array.isArray(gDict) && gDict[study]) {
        gVals = filterNoneLike(Array.isArray(gDict[study]) ? gDict[study] : [gDict[study]]);
      }
      // Skip empty or zero-only
      if (!gVals.length) continue;
      if (gVals.length === 1 && (gVals[0] === 0 || gVals[0] === '0')) continue;

      studyHtml += `<div class="gender-line"><span class="gender-label">${g}:</span> ${gVals.map(v => esc(String(v))).join(', ')}</div>`;
    }

    studyHtml += '</div>';
    parts.push(studyHtml);
  }

  // Also render studies from ev that are NOT in evg study keys
  if (evIsDict) {
    for (const [study, vals] of Object.entries(ev)) {
      if (studyKeys.has(study)) continue;  // already rendered above
      const filtered = filterNoneLike(Array.isArray(vals) ? vals : [vals]);
      if (filtered.length) {
        parts.push(`<div class="sub-block"><span class="sub-block-header">${esc(study)}:</span> ${filtered.map(v => esc(String(v))).join(', ')}</div>`);
      }
    }
  }

  return parts.join('') || '<span class="empty-val">(empty)</span>';
}

// ---- Tooltip ----
const tooltipEl = document.getElementById('tooltip');

function showTooltip(paperId, field, x, y) {
  const fd = papers[paperId]?.[field];
  const gt = gtDisplay[paperId]?.[field];

  // If no extracted data AND no GT info, nothing to show
  if (!fd && gt === undefined) { tooltipEl.style.display = 'none'; return; }

  let html = '';
  if (fd) {
    // best_indices
    html += `<div><span class="tt-label">best_indices:</span> ${formatBestIndices(fd.best_indices)}</div>`;
    // reason
    if (fd.reason) {
      html += `<div class="tt-section"><span class="tt-label">reason:</span> ${esc(fd.reason)}</div>`;
    }
  } else {
    html += `<div><span class="tt-label" style="color:#888">No values extracted for this field.</span></div>`;
  }
  // ground truth
  if (gt !== undefined) {
    html += `<div class="tt-gt"><span class="tt-label">ground_truth:</span> ${esc(gt)}</div>`;
  }

  tooltipEl.innerHTML = html;
  tooltipEl.style.display = 'block';

  // Position
  const rect = tooltipEl.getBoundingClientRect();
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let left = x + 12;
  let top = y + 12;
  if (left + rect.width > vw - 10) left = x - rect.width - 12;
  if (top + rect.height > vh - 10) top = y - rect.height - 12;
  if (left < 0) left = 10;
  if (top < 0) top = 10;
  tooltipEl.style.left = left + 'px';
  tooltipEl.style.top = top + 'px';
}

function hideTooltip() {
  tooltipEl.style.display = 'none';
  tooltipEl.classList.remove('pinned');
}

// ---- Build table ----
function buildTable(visiblePapers) {
  const headerRow = document.getElementById('headerRow');
  const tbody = document.getElementById('tableBody');

  // Header
  headerRow.innerHTML = '<th>Paper</th>' + fields.map(f => `<th title="${esc(f)}">${esc(f)}</th>`).join('');

  // Body
  const rows = [];
  for (const pid of visiblePapers) {
    const pdata = papers[pid];
    let tr = `<tr data-paper="${esc(pid)}"><td title="${esc(pid)}">${esc(pid)}</td>`;
    for (const field of fields) {
      const fd = pdata[field];
      const match = comparison[pid]?.[field] || 'neutral';
      const cellContent = renderCell(fd);
      tr += `<td><div class="cell-block match-${match}" data-paper="${esc(pid)}" data-field="${esc(field)}">${cellContent}</div></td>`;
    }
    tr += '</tr>';
    rows.push(tr);
  }
  tbody.innerHTML = rows.join('');

  document.getElementById('paperCount').textContent = `${visiblePapers.length} papers`;

  // Attach events
  attachCellEvents();
}

function attachCellEvents() {
  document.querySelectorAll('.cell-block').forEach(block => {
    block.addEventListener('mouseenter', (e) => {
      if (pinnedTooltip) return; // don't override pinned
      const pid = block.dataset.paper;
      const field = block.dataset.field;
      showTooltip(pid, field, e.clientX, e.clientY);
    });
    block.addEventListener('mousemove', (e) => {
      if (pinnedTooltip) return;
      const pid = block.dataset.paper;
      const field = block.dataset.field;
      showTooltip(pid, field, e.clientX, e.clientY);
    });
    block.addEventListener('mouseleave', () => {
      if (!pinnedTooltip) hideTooltip();
    });
    block.addEventListener('click', (e) => {
      e.stopPropagation();
      const pid = block.dataset.paper;
      const field = block.dataset.field;

      if (pinnedTooltip && pinnedTooltip.paperId === pid && pinnedTooltip.field === field) {
        // Unpin
        pinnedTooltip = null;
        hideTooltip();
        block.classList.remove('pinned');
      } else {
        // Unpin old
        if (pinnedTooltip) {
          document.querySelectorAll('.cell-block.pinned').forEach(b => b.classList.remove('pinned'));
        }
        // Pin new
        pinnedTooltip = { paperId: pid, field: field };
        block.classList.add('pinned');
        showTooltip(pid, field, e.clientX, e.clientY);
        tooltipEl.classList.add('pinned');
      }
    });
  });
}

// Click elsewhere to unpin
document.addEventListener('click', (e) => {
  if (pinnedTooltip && !e.target.closest('.cell-block') && !e.target.closest('.tooltip-box')) {
    pinnedTooltip = null;
    hideTooltip();
    document.querySelectorAll('.cell-block.pinned').forEach(b => b.classList.remove('pinned'));
  }
});

// ---- Controls ----
const viewMode = document.getElementById('viewMode');
const paperSelect = document.getElementById('paperSelect');
const searchBox = document.getElementById('searchBox');

// Populate paper select
paperIds.forEach(pid => {
  const opt = document.createElement('option');
  opt.value = pid;
  opt.textContent = pid;
  paperSelect.appendChild(opt);
});

function refresh() {
  const mode = viewMode.value;
  const search = searchBox.value.trim().toLowerCase();

  let visible;
  if (mode === 'single') {
    paperSelect.style.display = '';
    visible = [paperSelect.value];
  } else {
    paperSelect.style.display = 'none';
    visible = paperIds;
  }

  if (search) {
    visible = visible.filter(pid => pid.toLowerCase().includes(search));
  }

  // Reset tooltip state
  pinnedTooltip = null;
  hideTooltip();

  buildTable(visible);
}

viewMode.addEventListener('change', refresh);
paperSelect.addEventListener('change', refresh);
searchBox.addEventListener('input', refresh);

// Initial render
refresh();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a self-contained HTML dashboard for extraction pipeline results."
    )
    parser.add_argument("--results_root", required=True,
                        help="Path to the results root folder containing paper subfolders.")
    parser.add_argument("--ground_truth", default=None,
                        help="Path to the ground_truth.json file (optional).")
    parser.add_argument("--out", default="dashboard.html",
                        help="Output path for the generated HTML dashboard.")
    args = parser.parse_args()

    # Resolve paths
    results_root = os.path.abspath(args.results_root)
    if not os.path.isdir(results_root):
        print(f"Error: results_root '{results_root}' is not a directory.")
        return

    # Load results
    print(f"Loading results from: {results_root}")
    papers, all_fields = load_results(results_root)
    print(f"  Found {len(papers)} papers, {len(all_fields)} fields")

    # Load ground truth
    gt_data = None
    if args.ground_truth:
        gt_path = os.path.abspath(args.ground_truth)
        if os.path.isfile(gt_path):
            print(f"Loading ground truth from: {gt_path}")
            gt_data = load_ground_truth(gt_path)
            print(f"  Found {len(gt_data)} ground truth entries")
        else:
            print(f"Warning: ground_truth file '{gt_path}' not found, skipping.")

    # Build comparison
    comparison = build_comparison(papers, all_fields, gt_data)
    gt_display = {}
    if gt_data:
        gt_display = build_gt_display(gt_data)

    # Generate HTML
    html = generate_html(papers, all_fields, comparison, gt_display, gt_data)

    # Write output
    out_path = os.path.abspath(args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard written to: {out_path}")


if __name__ == "__main__":
    main()
