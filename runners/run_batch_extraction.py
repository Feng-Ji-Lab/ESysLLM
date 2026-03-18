import argparse
import sys

# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config_loader import ConfigLoader
from src.pipeline.execution import PipelineExecutor

def main():
    parser = argparse.ArgumentParser(description="Step 4: Batch Extraction & Aggregation")
    parser.add_argument("--start", type=int, default=0, help="Start index (0-based)")
    parser.add_argument("--end", type=int, default=10, help="End index (exclusive)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output")
    parser.add_argument("--input_processed", default="processed_sections_test", help="Path to preprocessed sections root")
    parser.add_argument("--output_final", default="output/test_run", help="Path to save final results")
    parser.add_argument("--skip", nargs="*", default=[], help="List of paper names to skip")
    
    args = parser.parse_args()
    
    print(f"Initializing Batch Execution: {args.start} to {args.end}")
    print(f"Input: {args.input_processed}")
    print(f"Output: {args.output_final}")
    print(f"Skipping: {args.skip}")
    
    try:
        config = ConfigLoader()
        runner = PipelineExecutor(config, args.output_final)
        
        runner.run_batch(
            preprocessed_dir=args.input_processed,
            start_index=args.start,
            end_index=args.end,
            overwrite=args.overwrite,
            excluded_papers=args.skip
        )
        print("Batch execution finished.")
        
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
