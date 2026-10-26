import os
import json
import logging
import traceback
from src.preprocessor import JSONPaperParser

class PreprocessingPipeline:
    def __init__(self, output_root: str, log_file: str = "pipeline_preprocessing.log"):
        self.output_root = output_root
        
        # Setup Logger
        self.logger = logging.getLogger("PreprocessingPipeline")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates if re-initialized
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
            
        # File Handler
        fh = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(ch)

    def run(self, papers_dir: str, start_index: int = 0, end_index: int = None, overwrite: bool = False):
        """
        Runs preprocessing for a subset of paper directories.
        
        Args:
            papers_dir: Directory containing paper subdirectories.
            start_index: Index to start processing from.
            end_index: Index to stop processing at (exclusive). None = all.
            overwrite: If True, re-processes even if output folder exists.
            
        Returns:
            dict: Mapping of {paper_name: output_processed_path}
        """
        if not os.path.exists(self.output_root):
            os.makedirs(self.output_root)

        if not os.path.exists(papers_dir):
            raise FileNotFoundError(f"Papers directory not found: {papers_dir}")

        # List all subdirectories (papers)
        # Requirement: Support repo style (folder/folder.json)
        paper_names = sorted([d for d in os.listdir(papers_dir) if os.path.isdir(os.path.join(papers_dir, d))])
        
        if not paper_names:
            self.logger.warning(f"Warning: No paper directories found in {papers_dir}")
            return {}
        
        # Determine Batch
        if end_index is None or end_index > len(paper_names):
            end_index = len(paper_names)
        if start_index < 0: 
            start_index = 0
            
        batch_papers = paper_names[start_index:end_index]
        
        self.logger.info("-" * 40)
        self.logger.info(f"Starting Preprocessing Batch: Papers {start_index+1} to {end_index} (Total: {len(batch_papers)})")
        self.logger.info("-" * 40)
        
        results = {}

        for i, paper_name in enumerate(batch_papers):
            idx = start_index + i + 1
            
            # Safe Name Printing
            display_name = paper_name
            try:
                display_name.encode('utf-8')
            except UnicodeEncodeError:
                display_name = paper_name.encode('ascii', 'replace').decode('ascii')
                
            self.logger.info(f"[{idx}/{len(paper_names)}] Preprocessing: {display_name}...")
            
            paper_path = os.path.join(papers_dir, paper_name)
            paper_out_dir = os.path.join(self.output_root, paper_name)
            
            # Check overwrite
            if os.path.exists(paper_out_dir) and not overwrite:
                 # Check if it has content
                 if os.listdir(paper_out_dir):
                     self.logger.info(f"  -> Skipping (Output exists)")
                     results[paper_name] = paper_out_dir
                     continue

            try:
                parser = JSONPaperParser(paper_path)
                sections = parser.parse_sections()
                
                if not os.path.exists(paper_out_dir):
                    os.makedirs(paper_out_dir)
                    
                for sec_id, sec_data in sections.items():
                    fname = f"{sec_id}.json"
                    out_path = os.path.join(paper_out_dir, fname)
                    with open(out_path, 'w', encoding='utf-8') as f:
                        json.dump(sec_data, f, indent=2, ensure_ascii=False)
                        
                self.logger.info(f"  -> Saved {len(sections)} sections.")
                results[paper_name] = paper_out_dir
                
            except Exception as e:
                self.logger.error(f"  -> ERROR: {e}")
                self.logger.debug(traceback.format_exc())
                
        return results
