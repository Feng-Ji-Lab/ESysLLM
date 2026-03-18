
import os
import json

# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.validator import Validator

# OUTPUT_DIR = "D:/PhD/llm_meta_analysis_new/output/phase1"
# OUTPUT_DIR = "output/claude_haiku_4.5"
OUTPUT_DIR = "meta_intelligence/output"
GT_PATH = "meta_intelligence/ground_truth.json"

import sys

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
    
    if not os.path.exists(OUTPUT_DIR):
        print(f"Output directory not found: {OUTPUT_DIR}")
        return

    papers = sorted([d for d in os.listdir(OUTPUT_DIR) if os.path.isdir(os.path.join(OUTPUT_DIR, d))])
    
    print(f"Verifying {len(papers)} papers against Ground Truth...")
    print("="*60)
    
    for paper in papers:
        print(f"\nPaper: {paper}")
        res_path = os.path.join(OUTPUT_DIR, paper, "final_results.json")
        
        if not os.path.exists(res_path):
            print("  [SKIP] final_results.json not found (Extraction might have failed).")
            continue
            
        try:
            with open(res_path, 'r', encoding='utf-8') as f:
                final_results = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Could not load JSON: {e}")
            continue
            
        # Get GT
        gt_data = validator.get_ground_truth_for_paper(paper)
        
        if not gt_data:
            print("  [WARN] No Ground Truth found matching this paper name.")
            continue
            
        # Validate
        is_valid, errors = validator.validate(final_results, gt_data)
        
        if is_valid:
            print("  [PASS] All fields match.")
        else:
            print(f"  [FAIL] Found {len(errors)} mismatches:")
            for e in errors:
                print(f"    - {e}")

if __name__ == "__main__":
    main()
