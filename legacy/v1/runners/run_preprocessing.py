import os
import json

# Auto-injected to allow importing from src and config
import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.chdir(project_root)

from src.preprocessor import JSONPaperParser

INPUT_ROOTS = ["output_comparison_no_llm", "output_comparison_llm"]
OUTPUT_ROOT = "processed_sections"

def main():
    if not os.path.exists(OUTPUT_ROOT):
        os.makedirs(OUTPUT_ROOT)

    for input_root in INPUT_ROOTS:
        if not os.path.exists(input_root):
             print(f"Warning: Input directory {input_root} does not exist. Skipping.")
             continue
             
        # list all subdirs
        paper_dirs = [d for d in os.listdir(input_root) if os.path.isdir(os.path.join(input_root, d))]
        
        for paper_name in paper_dirs:
            print(f"Processing {paper_name} from {input_root}...")
            paper_path = os.path.join(input_root, paper_name)
            
            try:
                parser = JSONPaperParser(paper_path)
                sections = parser.parse_sections()
                
                # Save output
                # Use source folder name as subfolder in processed_sections to avoid overwrite
                # e.g. processed_sections/output_comparison_no_llm/1Todd2019
                
                source_name = os.path.basename(input_root)
                paper_out_dir = os.path.join(OUTPUT_ROOT, source_name, paper_name)
                
                if not os.path.exists(paper_out_dir):
                    os.makedirs(paper_out_dir)
                    
                for sec_id, sec_data in sections.items():
                    fname = f"{sec_id}.json"
                    out_path = os.path.join(paper_out_dir, fname)
                    with open(out_path, 'w', encoding='utf-8') as f:
                        json.dump(sec_data, f, indent=2, ensure_ascii=False)
                        
                print(f"  -> Saved {len(sections)} sections to {paper_out_dir}")
            except Exception as e:
                print(f"  ERROR processing {paper_name}: {e}")

if __name__ == "__main__":
    main()
