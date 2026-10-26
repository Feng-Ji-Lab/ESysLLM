import os
import json
import sys

# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.validator import Validator

# Configuration
GT_PATH = "test/ground_truth.json"
TARGET_PAPERS = ["1Atari2016", "1Benford2014", "1Cotter2015", "1Iannantuono2012", "1Swami2009check"]

# (Label, Path)
EXPERIMENTS = [
    ("Claude Haiku 4.5 (T=0)", "output/claude_haiku_4.5"),
    ("Claude Haiku 4.5 (T=0.2)", "output_temp_diff/claude-haiku-4-5_0.2"),
    ("Claude Haiku 4.5 (T=0.4)", "output_temp_diff/claude-haiku-4-5_0.4"),
    ("Gemini 2.5 Flash (T=0)", "output/gemini_2.5_flash"),
    ("Gemini 2.5 Flash (T=0.2)", "output_temp_diff/gemini-2.5-flash_0.2"),
    ("Gemini 2.5 Flash (T=0.4)", "output_temp_diff/gemini-2.5-flash_0.4"),
    ("GPT 5 Mini (T=0)", "output/gpt_5_mini"),
    ("GPT 5 Mini (T=0.2)", "output_temp_diff/gpt-5-mini_0.2"),
    ("GPT 5 Mini (T=0.4)", "output_temp_diff/gpt-5-mini_0.4"),
]

def calculate_precision_recall(correct, incorrect, missing):
    precision = correct / (correct + incorrect) if (correct + incorrect) > 0 else 0.0
    recall = correct / (correct + missing) if (correct + missing) > 0 else 0.0
    return precision, recall

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if not os.path.exists(GT_PATH):
        print(f"Critical Error: Ground Truth not found at {GT_PATH}")
        return

    # Load validation_targets
    try:
        with open(os.path.join(project_root, "config", "settings.json"), "r", encoding="utf-8") as f:
            settings = json.load(f)
        validation_targets = settings.get("validation_targets", [])
    except Exception as e:
        print(f"Warning: Could not load config/settings.json: {e}")
        validation_targets = []

    validator = Validator(GT_PATH, code_book_path=os.path.join(project_root, "config", "code_book.json"), threshold=0.05, target_fields=validation_targets)
    
    for label, dir_path in EXPERIMENTS:
        full_dir = os.path.join(project_root, dir_path)
        if not os.path.exists(full_dir):
            print(f"Directory missing, skipping {label}: {full_dir}")
            continue
            
        print(f"Evaluating {label}...")
        
        correct_total = 0
        incorrect_total = 0
        missing_total = 0
        
        for paper in TARGET_PAPERS:
            res_path = os.path.join(full_dir, paper, "final_results.json")
            
            if not os.path.exists(res_path):
                # print(f"  [MISSING] {res_path}")
                final_results = {}
            else:
                try:
                    with open(res_path, 'r', encoding='utf-8') as f:
                        final_results = json.load(f)
                except Exception as e:
                    print(f"  [ERROR] Could not load JSON for {paper}: {e}")
                    final_results = {}
                
            # Get GT
            gt_data = validator.get_ground_truth_for_paper(paper)
            
            if not gt_data:
                continue
                
            organized_ext = validator._normalize_extracted(final_results)
            
            # Compare each field
            for gt_field, gt_vals in gt_data.items():
                if gt_field in ["ID", "filename"]: continue
                
                # Resolve Extracted Field Key
                ext_field = validator.key_mapping.get(gt_field, gt_field)
                
                # Filter Logic: Check if field is in target_fields
                if validator.target_fields and ext_field not in validator.target_fields:
                    continue
                
                # Skip if GT is empty/none
                if validator._is_gt_empty(gt_vals): continue
                
                # Check if Extracted has field
                if ext_field not in organized_ext:
                    missing_total += 1
                    continue

                ext_vals = organized_ext[ext_field]
                
                # Validation logic
                is_correct = True
                
                # Case A: Dictionary (Gender Split)
                if isinstance(gt_vals, dict) and "male" in gt_vals:
                    if not isinstance(ext_vals, dict):
                        if isinstance(ext_vals, list):
                             ext_vals = { "male": [], "female": [], "total": ext_vals }
                    
                    normalized_gt = {
                        "male": validator._flatten_values(gt_vals.get("male", [])),
                        "female": validator._flatten_values(gt_vals.get("female", [])),
                        "total": validator._flatten_values(gt_vals.get("total", [])),
                        "other": validator._flatten_values(gt_vals.get("other", []))
                    }

                    for gender in ["male", "female", "total"]:
                        gt_g_list = normalized_gt.get(gender, [])
                        if validator._is_gt_empty(gt_g_list): continue

                        gt_scalars = validator._flatten_to_scalars(gt_g_list)
                        ext_g_list = ext_vals.get(gender, [])
                        
                        if not validator._values_subset(gt_scalars, ext_g_list):
                             is_correct = False
                             break

                # Case B: List (Enum/Scalar)
                else:
                    gt_scalars = validator._flatten_to_scalars(gt_vals)
                    if not isinstance(ext_vals, list): ext_vals = [ext_vals]
                    
                    if not validator._values_subset(gt_scalars, ext_vals):
                        is_correct = False
                
                if is_correct:
                    correct_total += 1
                else:
                    incorrect_total += 1
        
        print(f"  Correct: {correct_total}")
        print(f"  Incorrect: {incorrect_total}")
        print(f"  Missing: {missing_total}")
        precision, recall = calculate_precision_recall(correct_total, incorrect_total, missing_total)
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall: {recall:.4f}")
        print("="*60)

if __name__ == "__main__":
    main()
