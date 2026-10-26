
# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.config_loader import ConfigLoader
from src.pipeline.interface import UserInterface
import sys
import os

print("Testing User Interface Preview...")
try:
    c = ConfigLoader()
    ui = UserInterface(c)
    ui.display_preview()
    print("SUCCESS: Interface displayed without crashing.")
except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
