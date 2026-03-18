
# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config_loader import ConfigLoader
import sys

print("Testing Real Config Validation...")
try:
    c = ConfigLoader()
    print("SUCCESS: Real config loaded and validated.")
    print(f"Papers Path: {c.papers_json_path}")
    print(f"Requested Fields: {len(c.requested_fields)}")
except Exception as e:
    print(f"FAILURE: {e}")
    sys.exit(1)
