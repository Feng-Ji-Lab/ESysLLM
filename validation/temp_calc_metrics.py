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

def calculate_precision_recall(correct, incorrect, missing):
    precision = correct / (correct + incorrect) if (correct + incorrect) > 0 else 0.0
    recall = correct / (correct + missing) if (correct + missing) > 0 else 0.0
    return precision, recall

def eval_dataset(dataset_dir, target_fields=None, skip_papers=None):
    if skip_papers is None:
        skip_papers = []
        
    gt_path = os.path.join(dataset_dir, "ground_truth.json")
    if not os.path.exists(gt_path):
        print(f"GT not found: {gt_path}")
        return
    
    # Initialize validator. If target_fields is None, it uses all fields in GT
    validator = Validator(gt_path, code_book_path=os.path.join(project_root, "config", "code_book.json"), threshold=0.05, target_fields=target_fields)

    output_dir = os.path.join(dataset_dir, "output")
    if not os.path.exists(output_dir):
        print(f"Output directory not found: {output_dir}")
        return

    papers = sorted([d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))])
    
    correct_total = 0
    incorrect_total = 0
    missing_total = 0
    
    for paper in papers:
        if paper in skip_papers:
            continue
            
        res_path = os.path.join(output_dir, paper, "final_results.json")
        if not os.path.exists(res_path):
            final_results = {}
        else:
            try:
                with open(res_path, 'r', encoding='utf-8') as f:
                    final_results = json.load(f)
            except Exception as e:
                print(f"  [ERROR] Could not load JSON for {paper}: {e}")
                final_results = {}
                
        gt_data = validator.get_ground_truth_for_paper(paper)
        if not gt_data:
            continue
            
        organized_ext = validator._normalize_extracted(final_results)
        
        for gt_field, gt_vals in gt_data.items():
            if gt_field in ["ID", "filename"]: continue
            
            ext_field = validator.key_mapping.get(gt_field, gt_field)
            if validator.target_fields and ext_field not in validator.target_fields:
                continue
            
            if validator._is_gt_empty(gt_vals): continue
            
            if ext_field not in organized_ext:
                missing_total += 1
                continue

            ext_vals = organized_ext[ext_field]
            is_correct = True
            
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
            else:
                gt_scalars = validator._flatten_to_scalars(gt_vals)
                if not isinstance(ext_vals, list): ext_vals = [ext_vals]
                
                if not validator._values_subset(gt_scalars, ext_vals):
                    is_correct = False
            
            if is_correct:
                correct_total += 1
            else:
                incorrect_total += 1
    
    print(f"Dataset: {dataset_dir}")
    print(f"  Correct: {correct_total}")
    print(f"  Incorrect: {incorrect_total}")
    print(f"  Missing: {missing_total}")
    precision, recall = calculate_precision_recall(correct_total, incorrect_total, missing_total)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall: {recall:.4f}")
    print(f"  F1: {f1:.4f}")
    print("="*60)

if __name__ == "__main__":
    eval_dataset("meta_gratitude_loneliness", target_fields=['r', 'N', 'female', 'M_age', 'SD_age', 'usa_vs_other'])
    eval_dataset("meta_intelligence", target_fields=["SAMPLE SIZE", "ES", "Mage", "IQ modality", "IQ Aspect", "Creativity Measures", "Domain classified"])
