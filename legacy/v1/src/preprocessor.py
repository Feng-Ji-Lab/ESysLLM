import json
import os
import re
import pandas as pd
from typing import Dict, List, Any, Optional

class JSONPaperParser:
    def __init__(self, paper_dir: str):
        """
        Initialize the parser for a specific paper directory.
        Args:
            paper_dir: Path to the directory containing the paper's JSON and manifests
                       (e.g., .../output_comparison_no_llm/1Todd2019)
        """
        self.paper_dir = paper_dir
        self.paper_name = os.path.basename(paper_dir)
        self.json_path = os.path.join(paper_dir, f"{self.paper_name}.json")
        self.figures_manifest_path = os.path.join(paper_dir, "figures", "manifest.json")
        self.tables_manifest_path = os.path.join(paper_dir, "tables", "manifest.json")
        
        self.main_json_data = self._load_json(self.json_path)
        self.figures_metadata = self._load_figures_manifest()
        self.tables_metadata = self._load_tables_manifest()
        
        # Block ID to Text Content mapping for quick lookup (for captions/notes)
        self.block_id_to_text = {}
        # Block ID to Block object mapping
        self.block_map = {}
        self._index_blocks(self.main_json_data)

    def _load_json(self, path: str) -> Dict:
        if not os.path.exists(path):
            print(f"Warning: JSON file not found: {path}")
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_figures_manifest(self) -> List[Dict]:
        if not os.path.exists(self.figures_manifest_path):
            return []
        try:
            with open(self.figures_manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading figures manifest {self.figures_manifest_path}: {e}")
            return []

    def _load_tables_manifest(self) -> List[Dict]:
        if not os.path.exists(self.tables_manifest_path):
            return []
        try:
            df = pd.read_csv(self.tables_manifest_path)
            return df.to_dict('records')
        except Exception as e:
            print(f"Error loading tables manifest {self.tables_manifest_path}: {e}")
            return []

    def _index_blocks(self, block: Dict):
        """Recursively map block IDs to their content for O(1) lookup."""
        if 'id' in block:
            self.block_map[block['id']] = block
            # Store all block text content for lookup regardless of type
            raw_text = self._strip_html(block.get('html', ''))
            if raw_text:
                self.block_id_to_text[block['id']] = raw_text

        for child in block.get('children', []) or []:
            self._index_blocks(child)

    def _strip_html(self, html: str) -> str:
        """Remove HTML tags to get raw text."""
        if not html:
            return ""
        # Remove specific tags but keep content
        text = re.sub(r'<[^>]+>', '', html)
        return text.strip()

    def parse_sections(self) -> Dict[str, Dict]:
        sections = {}
        all_blocks = [] # Track strict order of all blocks for global matching

        # 1. Traverse and Collect Blocks
        # Initialize mapping to track unique section names per header ID
        self.header_to_section_map = {}
        self.header_to_section_title = {}
        
        for page in self.main_json_data.get('children', []):
            self._process_block_recursive(page, sections, all_blocks)
            
        # 2. Global Manifest Resolution (Pre-link images/tables)
        self._link_manifest_to_blocks(all_blocks, sections)

        # 3. Finalize Sections (Merge text, format output)
        inputs = {}
        # Use simple counter to preserve document order
        for i, (old_sec_id, sec_data) in enumerate(sections.items(), 1):
            # Use 3-digit padding (e.g., 001) to ensure correct filesystem sorting order
            new_sec_id = f"{i:03d}_{old_sec_id}"
            
            final_data = self._finalize_section(sec_data)
            final_data['section_id'] = new_sec_id
            
            inputs[new_sec_id] = final_data
            
        return inputs

    def _process_block_recursive(self, block: Dict, sections: Dict, all_blocks: List[Dict]):
        block_type = block.get('block_type')
        
        # Skip container pages (recurse)
        if block_type == 'Page':
            for child in block.get('children', []) or []:
                self._process_block_recursive(child, sections, all_blocks)
            return

        # Skip Headers/Footers
        if block_type in ['PageHeader', 'PageFooter']:
            return

        # Handle Container Groups (TableGroup, FigureGroup)
        if block_type in ['TableGroup', 'FigureGroup']:
             for child in block.get('children', []) or []:
                self._process_block_recursive(child, sections, all_blocks)
             return

        # Determine Section ID
        hierarchy = block.get('section_hierarchy', {})
        section_id = "general"
        section_title = "General / Front Matter"
        
        if hierarchy:
            sorted_levels = sorted(hierarchy.keys(), key=lambda x: int(x))
            deepest_level = sorted_levels[-1]
            header_block_id = hierarchy[deepest_level]
            
            # Logic Update: Ensure unique section_id for each unique header_block_id
            # Check if we've already assigned a section_id to this header_id
            if hasattr(self, 'header_to_section_map') and header_block_id in self.header_to_section_map:
                section_id = self.header_to_section_map[header_block_id]
                section_title = self.header_to_section_title[header_block_id]
            else:
                # New Header encountered
                if header_block_id in self.block_id_to_text:
                    section_title = self.block_id_to_text[header_block_id]
                    base_id = self._make_safe_id(section_title)
                else:
                    section_title = "Unknown Section"
                    base_id = f"section_{header_block_id.replace('/', '_')}"
                
                # Check for collision in existing sections
                if base_id in sections:
                    # Collision detected! Find a suffix.
                    counter = 1
                    new_id = f"{base_id}_{counter}"
                    while new_id in sections:
                        counter += 1
                        new_id = f"{base_id}_{counter}"
                    section_id = new_id
                else:
                    section_id = base_id
                
                # Store mapping if stateful (Need to initialize maps in parse_sections)
                if hasattr(self, 'header_to_section_map'):
                   self.header_to_section_map[header_block_id] = section_id
                   self.header_to_section_title[header_block_id] = section_title

        if section_id not in sections:
            sections[section_id] = {
                "section_id": section_id,
                "title": section_title,
                "blocks": []
            }

        # Create Block Object
        new_block = None
        if block_type in ['Text', 'ListItem', 'SectionHeader']:
            text_content = self._strip_html(block.get('html', ''))
            if text_content:
                new_block = {
                    "type": "text",
                    "content": text_content,
                    "raw_html": block.get('html', ''),
                    "page": self._get_page_num(block.get('id', ''))
                }

        elif block_type == 'Picture':
            new_block = {
                "type": "image",
                "block_id": block['id'],
                "page": self._get_page_num(block['id'])
            }

        elif block_type == 'Table':
             new_block = {
                "type": "table",
                "block_id": block['id'],
                "page": self._get_page_num(block['id'])
            }
            
        if new_block:
             sections[section_id]['blocks'].append(new_block)
             all_blocks.append(new_block) # Add to global list for matching

    def _link_manifest_to_blocks(self, all_blocks: List[Dict], sections: Dict[str, Dict] = None):
        """Match tables/images to their manifest entries. Inject orphans if missing."""
        # Helper: Map Page -> List of Section objects (references)
        # We'll use this to find where to put orphans.
        sections_by_page = {}
        if sections:
            for sec_id, sec_data in sections.items():
                # Estimate page of section by looking at its first block
                # Default to page 0
                page = 0
                for blk in sec_data['blocks']:
                    if 'page' in blk:
                        page = blk['page']
                        break
                if page not in sections_by_page:
                    sections_by_page[page] = []
                sections_by_page[page].append(sec_data)

        # 1. Map existing blocks by Type -> Page -> List of Blocks
        tables_by_page = {}
        images_by_page = {}
        
        for blk in all_blocks:
            page = blk.get('page', 0)
            if blk['type'] == 'table':
                if page not in tables_by_page: tables_by_page[page] = []
                tables_by_page[page].append(blk)
            elif blk['type'] == 'image':
                if page not in images_by_page: images_by_page[page] = []
                images_by_page[page].append(blk)
                
        # 2. Link Tables
        manifest_tables_by_page = {}
        for row in self.tables_metadata:
            p = row.get('page_index', 0)
            if p not in manifest_tables_by_page: manifest_tables_by_page[p] = []
            manifest_tables_by_page[p].append(row)
            
        # Match Tables
        for page, rows in manifest_tables_by_page.items():
            blocks = tables_by_page.get(page, [])
            
            for i, row in enumerate(rows):
                t_path = row.get('image_path', '')
                norm_path = t_path.replace("\\", "/").lower()
                if "figures/" not in norm_path and "tables/" not in norm_path:
                    continue

                if i < len(blocks):
                    # Link to existing block
                    blk = blocks[i]
                    blk['path'] = self._resolve_asset_path(t_path)
                    cid = row.get('caption_block_id')
                    blk['caption'] = self.block_id_to_text.get(cid) if cid and pd.notna(cid) else None
                    nid = row.get('note_block_id')
                    blk['note'] = self.block_id_to_text.get(nid) if nid and pd.notna(nid) else None
                    row['_linked'] = True
                else:
                    # ORPHAN TABLE: Inject it
                    cid = row.get('caption_block_id')
                    nid = row.get('note_block_id')
                    new_blk = {
                        "type": "table",
                        "block_id": f"orphan_table_{page}_{i}",
                        "page": page,
                        "path": self._resolve_asset_path(t_path),
                        "caption": self.block_id_to_text.get(cid) if cid and pd.notna(cid) else None,
                        "note": self.block_id_to_text.get(nid) if nid and pd.notna(nid) else None,
                        "is_orphan": True
                    }
                    all_blocks.append(new_blk)
                    # Append to section
                    if sections:
                        target_secs = sections_by_page.get(page, [])
                        if not target_secs:
                            # Fallback: try previous pages or just last section
                            target_secs = [list(sections.values())[-1]] if sections else []
                        if target_secs:
                            target_secs[-1]['blocks'].append(new_blk)
        
        # 3. Link Figures
        manifest_figs_by_page = {}
        for row in self.figures_metadata:
            p = row.get('page', 0)
            if p not in manifest_figs_by_page: manifest_figs_by_page[p] = []
            manifest_figs_by_page[p].append(row)
            
        for page, rows in manifest_figs_by_page.items():
            blocks = images_by_page.get(page, [])
            
            for i, row in enumerate(rows):
                # User constraint: Only use assets from "figures/" folder.
                f_path = row.get('file', '')
                if "figures/" not in f_path.replace("\\", "/").lower():
                    continue

                if i < len(blocks):
                    # Link to existing
                    blk = blocks[i]
                    blk['path'] = self._resolve_asset_path(f_path)
                    blk['caption'] = row.get('caption', '')
                    blk['note'] = None
                    row['_linked'] = True
                else:
                    # ORPHAN FIGURE: Inject it
                    # User added constraint: Only use figures from "figures/" folder.
                    # Ignore "images/" folder.
                    # Path typically: .../figures/file.png or .../images/file.png
                    figure_path = row.get('file', '')
                    if "figures/" not in figure_path.replace("\\", "/").lower():
                        continue

                    new_blk = {
                        "type": "image",
                        "block_id": f"orphan_fig_{page}_{i}",
                        "page": page,
                        "path": self._resolve_asset_path(figure_path),
                        "caption": row.get('caption', ''),
                        "note": None,
                        "is_orphan": True
                    }
                    all_blocks.append(new_blk)
                    # Append to section
                    if sections:
                        target_secs = sections_by_page.get(page, [])
                        if not target_secs:
                             # Fallback: try previous pages or just last section
                            target_secs = [list(sections.values())[-1]] if sections else []
                        if target_secs:
                            target_secs[-1]['blocks'].append(new_blk)
                
    def _finalize_section(self, section_data: Dict) -> Dict:
        """Merge text blocks and filter invalid assets."""
        final_blocks = []
        full_text_parts = []
        
        for blk in section_data['blocks']:
            if blk['type'] == 'text':
                full_text_parts.append(blk['content'])
                final_blocks.append(blk)
            else:
                # Exclude images/tables missing a valid path from the manifest
                if blk.get('path'):
                    final_blocks.append(blk)

        return {
            "section_id": section_data['section_id'],
            "title": section_data['title'],
            "text_content": "\n".join(full_text_parts),
            "blocks": final_blocks
        }

    def _get_page_num(self, block_id: str) -> int:
        # ID format: /page/0/Type/...
        try:
            parts = block_id.split('/')
            if len(parts) > 2 and parts[1] == 'page':
                return int(parts[2])
        except:
            pass
        return 0

    def _find_caption_in_text(self, blocks: List[Dict], current_index: int, keyword: str) -> Optional[str]:
        # Look behind and ahead 2 blocks
        start = max(0, current_index - 2)
        end = min(len(blocks), current_index + 3)
        for i in range(start, end):
            if blocks[i]['type'] == 'text':
                content = blocks[i]['content']
                if keyword in content:
                    return content
        return None

    def _make_safe_id(self, text: str) -> str:
        s = re.sub(r'[^a-zA-Z0-9_\s]', '', text)
        s = re.sub(r'\s+', '_', s)
        return s.lower()[:50]

    def _resolve_asset_path(self, asset_path: str) -> str:
        """
        Helper to get absolute path for an asset.
        Handles cases where the path is:
        1. Relative (e.g. "figures/fig1.png")
        2. Absolute local (already correct)
        3. Absolute foreign (e.g. from HPC "/project/.../PaperID/figures/...")
        """
        if not asset_path:
            return ""
            
        # 1. Normalize slashes
        clean_path = asset_path.replace("\\", "/")
        
        # 2. Check localized absolute path
        if os.path.exists(clean_path):
             return os.path.abspath(clean_path)
             
        if os.path.exists(os.path.join(self.paper_dir, clean_path)):
             return os.path.abspath(os.path.join(self.paper_dir, clean_path))

        # 3. Try to rebase foreign path
        # Strategies:
        # A. Look for "/figures/" or "/tables/"
        # B. Look for "/{paper_name}/"
        
        lower_path = clean_path.lower()
        
        # Strategy A: Standard folders
        keywords = ["/figures/", "/tables/", "/images/"]
        for kw in keywords:
            idx = lower_path.rfind(kw)
            if idx != -1:
                # Extract "figures/file.png" (no leading slash)
                relative_part = clean_path[idx+1:] 
                candidate = os.path.join(self.paper_dir, relative_part)
                if os.path.exists(candidate):
                    return os.path.abspath(candidate)
                
                # Fallback to appending the relative figures/tables path to the paper root.

        # Strategy B: Paper Name
        # clean_path: .../1Mendes2018/figures/...
        # self.paper_name: 1Mendes2018
        # We want everything AFTER the paper name folder.
        
        # Find /{paper_name}/ (case insensitive?)
        # Note: paper_name might be a substring of a filename, so check for directory separators
        
        pname = self.paper_name.lower()
        # Look for /pname/
        search_str = f"/{pname}/" 
        idx = lower_path.rfind(search_str)
        if idx != -1:
            # path is .../1Mendes2018/figures/...
            # We want headers + pname + / + remainder? 
            # No, we want absolute path to be self.paper_dir (which IS .../1Mendes2018) + remainder
            
            # clean_path[idx] is the slash before paper_name
            # clean_path[idx + len(search_str)] is start of remainder (e.g. "figures/...")
            
            relative_part = clean_path[idx + len(search_str):]
            candidate = os.path.join(self.paper_dir, relative_part)
            if os.path.exists(candidate):
                return os.path.abspath(candidate)
        
        # 4. Fallback: Just try basename?
        basename = os.path.basename(clean_path)
        # Try finding it recursively? No, too expensive.
        # Try in figures/ and tables/
        potential_subdirs = ["figures", "tables", "images", "."]
        for sub in potential_subdirs:
            candidate = os.path.join(self.paper_dir, sub, basename)
            if os.path.exists(candidate):
                return os.path.abspath(candidate)

        # 5. Give up, return original (but normalized) or absolute version of it
        # If it doesn't exist, we can't really fix it, but returning the joined path 
        # is the most "correct" intent if we assume it SHOULD be here.
        
        # Default behavior: Assume it's relative to paper dir if finding markers failed?
        # But if it started with /project/..., treating it as relative works nicely with join?
        # No, joining abspath ignores left side.
        
        # Fallback: estimate correct path using standard subdirectories
        for kw in keywords:
            idx = lower_path.rfind(kw)
            if idx != -1:
                 return os.path.abspath(os.path.join(self.paper_dir, clean_path[idx+1:]))
                 
        return clean_path
