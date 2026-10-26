"""Tests for manifest path normalization."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from mag.preprocessing.manifest_normalizer import normalize_manifests


def _write_tables_csv(p: Path, image_path: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["page_index", "image_path", "caption_block_id"])
        w.writeheader()
        w.writerow({"page_index": "6", "image_path": image_path, "caption_block_id": ""})


def test_normalizes_tables_csv_dotdot_paths(tmp_path):
    md = tmp_path / "paper"
    _write_tables_csv(md / "tables" / "manifest.json", "../mag_out/paper/tables/t0.png")
    normalize_manifests(md)
    rows = list(csv.DictReader((md / "tables" / "manifest.json").open()))
    assert rows[0]["image_path"] == "tables/t0.png"


def test_normalizes_figures_json_paths(tmp_path):
    md = tmp_path / "paper"
    (md / "figures").mkdir(parents=True)
    (md / "figures" / "manifest.json").write_text(
        json.dumps([{"page_index": 0, "image_path": "../x/paper/figures/f0.png", "caption": ""}])
    )
    normalize_manifests(md)
    data = json.loads((md / "figures" / "manifest.json").read_text())
    assert data[0]["image_path"] == "figures/f0.png"


def test_normalizes_figures_json_real_file_key(tmp_path):
    """Real Marker figures manifest stores the path under 'file' with an absolute
    remote path; it must be rebased too."""
    md = tmp_path / "paper"
    (md / "figures").mkdir(parents=True)
    (md / "figures" / "manifest.json").write_text(
        json.dumps([{"page": 3, "index": 1, "file": "/remote/out/paper/figures/f0.png"}])
    )
    normalize_manifests(md)
    data = json.loads((md / "figures" / "manifest.json").read_text())
    assert data[0]["file"] == "figures/f0.png"


def test_already_relative_path_unchanged(tmp_path):
    md = tmp_path / "paper"
    _write_tables_csv(md / "tables" / "manifest.json", "tables/t0.png")
    normalize_manifests(md)
    rows = list(csv.DictReader((md / "tables" / "manifest.json").open()))
    assert rows[0]["image_path"] == "tables/t0.png"


def test_missing_manifests_is_noop(tmp_path):
    md = tmp_path / "paper"
    md.mkdir()
    normalize_manifests(md)  # must not raise
