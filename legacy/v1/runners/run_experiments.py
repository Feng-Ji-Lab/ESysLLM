import os
import json
import logging

# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config_loader import ConfigLoader
from src.pipeline.execution import PipelineExecutor
from src.validator import Validator

papers_to_run = ["1Wasylkiw2014", "1Webb2014", "1Webb2015", "1Webb2018", "1da Silva2018"]
models_temps = [
    ("gemini-2.5-flash", 0.2),
    ("gemini-2.5-flash", 0.4),
    ("claude-haiku-4-5", 0.2),
    ("claude-haiku-4-5", 0.4),
    ("gpt-5-mini", 0.0),
    ("gpt-5-mini", 0.4)
]

# Load API keys
with open("config/apis.json", "r") as f:
    api_keys = json.load(f)

for model, temp in models_temps:
    print(f"\n{'='*50}\nRunning {model} at temp {temp}\n{'='*50}")
    
    # Update settings
    settings_path = "config/settings.json"
    with open(settings_path, "r") as f:
        settings = json.load(f)
    
    settings["model_name"] = model
    settings["temperature"] = temp
    if model in api_keys:
        settings["api_key"] = api_keys[model]
    
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=4)
        
    output_dir = f"output_temp_diff/{model}_{temp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Must re-init ConfigLoader so it reads the new settings.json
    config = ConfigLoader()
    runner = PipelineExecutor(config, output_dir, log_file=os.path.join(output_dir, "run.log"))
    
    # Get all papers to build exclude list
    preprocessed_dir = "processed_sections"
    all_papers = [d for d in os.listdir(preprocessed_dir) if os.path.isdir(os.path.join(preprocessed_dir, d))]
    excluded = [p for p in all_papers if p not in papers_to_run]
    
    runner.run_batch(
        preprocessed_dir=preprocessed_dir,
        start_index=0,
        end_index=len(all_papers),
        overwrite=True,
        excluded_papers=excluded
    )
    
    # Initialize Validator for this run
    target_fields = config.settings.get("validation_targets", [])
    validator = Validator("ground_truth.json", "config/code_book.json", threshold=0.05, target_fields=target_fields)
    
    # Run validation
    validation_results = {}
    for paper in papers_to_run:
        final_res_path = os.path.join(output_dir, paper, "final_results.json")
        if os.path.exists(final_res_path):
            with open(final_res_path, "r") as f:
                extracted = json.load(f)
            gt = validator.get_ground_truth_for_paper(paper)
            is_valid, errors = validator.validate(extracted, gt)
            validation_results[paper] = {
                "is_valid": is_valid,
                "errors": errors
            }
        else:
            validation_results[paper] = {
                "is_valid": False,
                "errors": ["final_results.json not found"]
            }
            
    with open(os.path.join(output_dir, "validation_summary.json"), "w") as f:
        json.dump(validation_results, f, indent=4)
    
    # Basic precision/recall metric output if desired
    # We can do a quick correct / total check
    correct = sum(1 for p in validation_results if validation_results[p]["is_valid"])
    total = len(papers_to_run)
    print(f"Validation complete for {model} at temp {temp}. Fully valid papers: {correct}/{total}")

print("All runs completed successfully!")
