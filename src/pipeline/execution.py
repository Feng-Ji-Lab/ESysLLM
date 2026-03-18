import os
import json
import logging
import traceback
from typing import List, Optional
from src.config_loader import ConfigLoader
from src.extractor import MetaAnalysisExtractor
from src.aggregator import Aggregator

class PipelineExecutor:
    def __init__(self, config: ConfigLoader, output_dir: str, log_file: str = "pipeline_execution.log"):
        self.config = config
        self.output_dir = output_dir
        
        # Setup Logger
        self.logger = logging.getLogger("PipelineExecutor")
        self.logger.setLevel(logging.INFO)
        
        # File Handler
        fh = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(ch)

        self.extractor = MetaAnalysisExtractor(config)
        self.aggregator = Aggregator(output_dir, config)

    def run_batch(self, preprocessed_dir: str, start_index: int, end_index: int, overwrite: bool = False, excluded_papers: List[str] = None):
        """
        Runs the pipeline for a subset of papers.
        output_dir/
            PaperName/
                (extracted sections...)
                candidates.json
                final_results.json
        """
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # Get list of papers from preprocessed directory
        # Structure: preprocessed_dir/PaperName/*.json
        all_papers = sorted([d for d in os.listdir(preprocessed_dir) if os.path.isdir(os.path.join(preprocessed_dir, d))])
        
        # Validate indices
        if start_index < 0: start_index = 0
        if end_index > len(all_papers): end_index = len(all_papers)
        
        batch_papers = all_papers[start_index:end_index]
        self.logger.info(f"Starting batch execution: Papers {start_index+1} to {end_index} (Total: {len(batch_papers)})")
        
        excluded_set = set(excluded_papers) if excluded_papers else set()
        
        for i, paper_name in enumerate(batch_papers):
            idx = start_index + i + 1
            
            if paper_name in excluded_set:
                self.logger.info(f"[{idx}/{len(all_papers)}] Skipping Excluded Paper: {paper_name}")
                continue
                
            self.logger.info(f"[{idx}/{len(all_papers)}] Processing Paper: {paper_name}")
            
            paper_input_dir = os.path.join(preprocessed_dir, paper_name)
            paper_output_dir = os.path.join(self.output_dir, paper_name)
            
            final_res_path = os.path.join(paper_output_dir, "final_results.json")
            
            # Check overwrite
            if os.path.exists(final_res_path) and not overwrite:
                self.logger.info(f"  -> Skipping {paper_name} (Output exists)")
                continue
                
            if not os.path.exists(paper_output_dir):
                os.makedirs(paper_output_dir)

            try:
                self._process_single_paper(paper_name, paper_input_dir, paper_output_dir)
                self.logger.info(f"  -> SUCCESS: {paper_name}")
            except Exception as e:
                self.logger.error(f"  -> FAILURE: {paper_name} - {str(e)}")
                self.logger.error(traceback.format_exc())
                # Do NOT retry. Continue to next paper as per user instruction.
                pass

    def _process_single_paper(self, paper_name: str, input_dir: str, output_dir: str):
        # 1. Gather Sections
        files = sorted([f for f in os.listdir(input_dir) if f.endswith(".json")])
        if not files:
            raise ValueError(f"No section JSONs found in {input_dir}")
            
        self.logger.info(f"  -> Phase 1: Extraction ({len(files)} sections)")
        
        # We need to collect ALL assets from ALL sections? 
        # No, extraction is per-section.
        
        all_candidates = {} 
        # Structure: { field_name: [ {value: ..., source: ..., confidence: ...}, ...] }
        # Or let Aggregator handle the collection?
        # Aggregator typically takes a list of candidates.
        
        # Let's clean output_dir first if overwrite? 
        # Creating a fresh aggregator for this paper
        
        for fname in files:
            fpath = os.path.join(input_dir, fname)
            section_name = fname.replace(".json", "")
            
            # Check if extracted file already exists? (Fine-grained resume)
            extracted_path = os.path.join(output_dir, f"{section_name}_extracted.json")
            # If we are in overwrite=True mode, we re-run.
            # If overwrite=False, we might skip file? 
            # But run_batch checks final_results.json. 
            # Let's assume re-run extraction if doing the paper.
            
            with open(fpath, 'r', encoding='utf-8') as f:
                sec_data = json.load(f)
            
            text = sec_data.get("text_content", "")
            
            # Asset Resolution logic (Copied from run_extraction.py but improved)
            # Preprocessor now gives ABSOLUTE paths in 'path'.
            # So we just need to verify existence.
            assets_to_process = []
            for blk in sec_data.get("blocks", []):
                if blk.get("type") in ["image", "table"]:
                    p = blk.get("path")
                    if p and os.path.exists(p):
                        assets_to_process.append({
                            "path": p,
                            "type": blk["type"],
                            "caption": blk.get("caption", "")
                        })
                    elif p:
                        self.logger.warning(f"    ! Asset missing: {p}")
            
            # Run Extraction
            # We assume extractor.extract_section is stateless regarding previous sections
            results_list = self.extractor.extract_section(text, assets=assets_to_process)
            
            # Save raw extracted
            with open(extracted_path, 'w', encoding='utf-8') as f:
                json.dump(results_list, f, indent=2)
                
        # 3. Aggregate
        self.logger.info("  -> Phase 2: Aggregation")
        
        # Aggregator needs to read the _extracted.json files from output_dir?
        # Aggregator.collect_candidates() iterates output_dir looking for *_extracted.json
        # So we just need to set the aggregator's output_dir (which we did in init, but wait...)
        # Aggregator init takes (root_output_dir, config). 
        # But wait, run_extraction.py passed `args.output_dir` as root.
        # And `args.output_dir` there was `extracted/PaperName`? 
        # Check run_extraction.py: `parser.add_argument("--output-dir", required=True)`
        # `os.makedirs(args.output_dir)` -> It assumes output-dir is SPECIFIC to the paper?
        # CLI call in batch script probably did: `python run_extraction.py --input .../Paper1 --output .../Output/Paper1`
        
        # In PipelineExecutor, we init Aggregator once.
        # Does Aggregator state depend on the specific paper folder?
        # Let's check Aggregator code.
        # viewed src/aggregator.py: `def __init__(self, output_dir: str, config: ConfigLoader): self.output_dir = output_dir`
        # `collect_candidates` uses `self.output_dir`.
        
        # Issue: If we init Aggregator once with ROOT dir, it scans ROOT dir?
        # We need a fresh Aggregator for each paper OR update its output_dir.
        # Updating output_dir is safer.
        
        self.aggregator.output_dir = output_dir # Update to current paper's output folder
        
        candidates = self.aggregator.collect_candidates()
        
        # Save candidates
        with open(os.path.join(output_dir, "candidates.json"), "w", encoding='utf-8') as f:
            json.dump(candidates, f, indent=2)
            
        final_results = self.aggregator.resolve_llm(candidates)
        
        # Save Final
        final_res_path = os.path.join(output_dir, "final_results.json")
        with open(final_res_path, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, indent=2)

