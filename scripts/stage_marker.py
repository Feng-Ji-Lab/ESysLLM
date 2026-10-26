"""Stage a paper's Marker output from the v1 reference checkout into a v2 run.

The v1 layout (test/papers/<id>/{<id>.json,<id>_meta.json,tables/,figures/,images/})
is identical to the v2 drop-in layout, so staging is a directory copy followed by
manifest normalization.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from mag.preprocessing.manifest_normalizer import normalize_manifests

V1_PAPERS = Path("/projects/code/llm_meta_analysis_new/test/papers")


def stage_paper(*, src_root: Path, paper_id: str, run_dir: Path) -> Path:
    """Copy <src_root>/<paper_id> -> <run_dir>/marker/<paper_id>, normalize, return it."""
    src = Path(src_root) / paper_id
    marker_dir = Path(run_dir) / "marker" / paper_id
    if marker_dir.exists():
        shutil.rmtree(marker_dir)
    shutil.copytree(src, marker_dir)
    normalize_manifests(marker_dir)
    return marker_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper-id", required=True)
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--src-root", default=V1_PAPERS, type=Path)
    a = ap.parse_args()
    marker_dir = stage_paper(src_root=a.src_root, paper_id=a.paper_id, run_dir=a.run_dir)
    print("staged:", marker_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
