
# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config_loader import ConfigLoader
from src.pipeline.preprocessing import PreprocessingPipeline
import os
import shutil

# Test Config
OUTPUT_ROOT = "meta_intelligence/processed_sections"
PAPERS_DIR = "meta_intelligence/papers_json"

print(f"Testing Preprocessing Pipeline on {PAPERS_DIR}...")

# Clean Previous Output
if os.path.exists(OUTPUT_ROOT):
    shutil.rmtree(OUTPUT_ROOT)    

pipeline = PreprocessingPipeline(OUTPUT_ROOT, log_file="test_preprocessing.log")

try:
    print("\n--- Test 1: Batch limiting (First 2 papers) ---")
    results_batch = pipeline.run(PAPERS_DIR, start_index=0, end_index=2, overwrite=True)
    
    if len(results_batch) != 2:
        print(f"FAILURE: Expected 2 papers, got {len(results_batch)}")
        exit(1)
    else:
        print("SUCCESS: Processed exactly 2 papers.")

    print("\n--- Test 2: Resume/Skip logic (Run same batch, should skip) ---")
    # Should be fast and skip
    results_skip = pipeline.run(PAPERS_DIR, start_index=0, end_index=2, overwrite=False)
    # We can check log file later, but for now just ensure it didn't crash
    print(f"SUCCESS: Re-run completed (Papers in result: {len(results_skip)})")

    print("\n--- Test 3: Full Run (Remaining papers) ---")
    # Run from index 2 onwards
    results_rest = pipeline.run(PAPERS_DIR, start_index=2, overwrite=False)
    print(f"SUCCESS: Processed remaining {len(results_rest)} papers.")
    
    # Check one output folder content
    if results_batch:
        first_paper = list(results_batch.keys())[0]
        out_dir = results_batch[first_paper]
        
        files = os.listdir(out_dir)
        json_files = [f for f in files if f.endswith(".json")]
        
        if len(json_files) > 0:
            print(f"[OK] Verified JSON sections generated for {first_paper} ({len(json_files)} files)")
        else:
            print(f"FAILURE: No JSON sections found in output for {first_paper}")
            exit(1)

except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
