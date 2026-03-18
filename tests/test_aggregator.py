
import os
import json

# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config_loader import ConfigLoader
from src.aggregator import Aggregator
from src.validator import Validator

# Configuration
TARGET_PAPER = "1Lemoine2018"
OUTPUT_BASE = "output/claude_haiku_4.5"
GT_PATH = "test/ground_truth.json"
CONFIG_ROOT = "."

def main():
    print(f"\n>>> Running Aggregation Test for {TARGET_PAPER}")
    
    # Files
    paper_dir = os.path.join(OUTPUT_BASE, TARGET_PAPER)
    candidates_path = os.path.join(paper_dir, "candidates.json")
    final_path = os.path.join(paper_dir, "final_results.json")
    
    if not os.path.exists(candidates_path):
        print(f"Error: {candidates_path} not found")
        print(f"Create json file: {candidates_path}")
        with open(candidates_path, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=2)

    # Load Config & Components
    config = ConfigLoader(CONFIG_ROOT)
    aggregator = Aggregator(paper_dir, config)
    validator = Validator(GT_PATH)

    # 1. Collect Candidates using updated logic
    print("  Collecting candidates from extraction files...")
    candidates = aggregator.collect_candidates()
    
    # Save updated candidates for inspection
    with open(candidates_path, 'w', encoding='utf-8') as f:
        json.dump(candidates, f, indent=2)
    print(f"  Saved regenerated candidates to {candidates_path}")

    # 2. Run Aggregation (with new consistency logic)
    print("  Running Resolve LLM...")
    try:
        final_results = aggregator.resolve_llm(candidates)
        
        # Save
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(final_results, f, indent=2)
        print(f"  Saved final results to {final_path}")
        
    except Exception as e:
        print(f"  Aggregation Error: {e}")
        return

    # 3. Validate
    print("  Validating...")
    gt_data = validator.get_ground_truth_for_paper(TARGET_PAPER)
    
    if not gt_data:
        print("  Warning: No GT found.")
    else:
        is_valid, errors = validator.validate(final_results, gt_data)
        if is_valid:
            print("  PASS: validation successful.")
        else:
            print(f"  FAIL: Found {len(errors)} errors:")
            for e in errors:
                print(f"    - {e}")

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Aggregation Test for a specific paper")
    parser.add_argument("--paper", type=str, default=TARGET_PAPER, help="Name of the paper folder")
    args = parser.parse_args()
    
    # Update TARGET_PAPER global or just pass to main?
    # Better to refactor main to take an argument
    TARGET_PAPER = args.paper
    main()
