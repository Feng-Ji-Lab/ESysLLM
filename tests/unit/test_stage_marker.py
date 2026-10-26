"""stage_marker copies a v1 paper dir into the v2 drop-in layout."""

from __future__ import annotations

import json

from scripts.stage_marker import stage_paper


def _make_v1_paper(root, paper_id):
    d = root / paper_id
    (d / "tables").mkdir(parents=True)
    (d / "figures").mkdir(parents=True)
    (d / f"{paper_id}.json").write_text(json.dumps({"block_type": "Document", "children": []}))
    (d / f"{paper_id}_meta.json").write_text("{}")
    (d / "tables" / "manifest.json").write_text("[]")
    (d / "figures" / "manifest.json").write_text("[]")
    return d


def test_stage_paper_copies_into_run_marker_dir(tmp_path):
    src_root = tmp_path / "v1"
    src_root.mkdir()
    paper_id = "1Hurst2017"
    _make_v1_paper(src_root, paper_id)
    run_dir = tmp_path / "run"

    marker_dir = stage_paper(src_root=src_root, paper_id=paper_id, run_dir=run_dir)

    assert marker_dir == run_dir / "marker" / paper_id
    assert (marker_dir / f"{paper_id}.json").is_file()
    assert (marker_dir / "tables" / "manifest.json").is_file()
    assert (marker_dir / "figures" / "manifest.json").is_file()


def test_stage_paper_is_idempotent(tmp_path):
    src_root = tmp_path / "v1"
    src_root.mkdir()
    paper_id = "1Hurst2017"
    _make_v1_paper(src_root, paper_id)
    run_dir = tmp_path / "run"
    stage_paper(src_root=src_root, paper_id=paper_id, run_dir=run_dir)
    # second call must not raise
    marker_dir = stage_paper(src_root=src_root, paper_id=paper_id, run_dir=run_dir)
    assert (marker_dir / f"{paper_id}.json").is_file()
