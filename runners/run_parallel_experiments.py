import os
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.validator import Validator

papers_to_run = ["1Atari2016", "1Benford2014", "1Cotter2015", "1Iannantuono2012", "1Swami2009check"]
models_temps = [
    # ("gemini-2.5-flash", 0)
    ("gemini-2.5-flash", 0.2),
    ("gemini-2.5-flash", 0.4),
    ("claude-haiku-4-5", 0.2),
    ("claude-haiku-4-5", 0.4),
    ("gpt-5-mini", 0.2),
    ("gpt-5-mini", 0.4)
]

# Load API keys
with open("config/apis.json", "r") as f:
    api_keys = json.load(f)

# Load settings to clone
settings_path = "config/settings.json"
with open(settings_path, "r") as f:
    base_settings = json.load(f)

def run_experiment(model, temp):
    exp_id = f"{model}_{temp}".replace(".", "_")
    output_dir = f"output_temp_diff/{model}_{temp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Create isolated settings
    exp_settings = dict(base_settings)
    exp_settings["model_name"] = model
    exp_settings["temperature"] = temp
    if model in api_keys:
        exp_settings["api_key"] = api_keys[model]
        
    exp_settings_path = f"config/settings_{exp_id}.json"
    with open(exp_settings_path, "w") as f:
        json.dump(exp_settings, f, indent=4)
        
    # Write a small script for this specific run
    runner_script = f"""
import os
import json
from src.config_loader import ConfigLoader
from src.pipeline.execution import PipelineExecutor
from src.validator import Validator

# Monkey-patch config loader to use our specific settings file
class CustomConfigLoader(ConfigLoader):
    def __init__(self):
        super(CustomConfigLoader, self).__init__()
        self.settings_path = "{exp_settings_path}"
        self.settings = self._load_json(self.settings_path)
        
config = CustomConfigLoader()
runner = PipelineExecutor(config, "{output_dir}", log_file=os.path.join("{output_dir}", "run.log"))

papers_to_run = {papers_to_run}
preprocessed_dir = "processed_sections"
all_papers = [d for d in os.listdir(preprocessed_dir) if os.path.isdir(os.path.join(preprocessed_dir, d))]
excluded = [p for p in all_papers if p not in papers_to_run]

runner.run_batch(
    preprocessed_dir=preprocessed_dir,
    start_index=0,
    end_index=len(all_papers),
    overwrite=False,
    excluded_papers=excluded
)

target_fields = config.settings.get("validation_targets", [])
validator = Validator("ground_truth.json", "config/code_book.json", threshold=0.05, target_fields=target_fields)

validation_results = {{}}
for paper in papers_to_run:
    final_res_path = os.path.join("{output_dir}", paper, "final_results.json")
    if os.path.exists(final_res_path):
        with open(final_res_path, "r") as f:
            extracted = json.load(f)
        gt = validator.get_ground_truth_for_paper(paper)
        is_valid, errors = validator.validate(extracted, gt)
        validation_results[paper] = {{"is_valid": is_valid, "errors": errors}}
    else:
        validation_results[paper] = {{"is_valid": False, "errors": ["final_results.json not found"]}}

with open(os.path.join("{output_dir}", "validation_summary.json"), "w") as f:
    json.dump(validation_results, f, indent=4)
"""
    script_path = f"run_{exp_id}.py"
    with open(script_path, "w") as f:
        f.write(runner_script)
        
    print(f"Started {model} @ {temp}")
    # run subprocess
    result = subprocess.run(["venv/bin/python", script_path], capture_output=True, text=True)
    
    # cleanup
    try:
        os.remove(exp_settings_path)
        os.remove(script_path)
    except:
        pass
        
    print(f"Finished {model} @ {temp}")
    return model, temp, result.returncode

print("Starting parallel execution of all experiments...")
start_time = time.time()
with ThreadPoolExecutor(max_workers=6) as executor:
    futures = [executor.submit(run_experiment, m, t) for m, t in models_temps]
    for future in futures:
        model, temp, rc = future.result()
        if rc != 0:
            print(f"WARNING: {model} run failed with return code {rc}")

print(f"All experiments finished in {time.time() - start_time:.2f} seconds.")
