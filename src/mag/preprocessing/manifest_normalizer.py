"""Rewrite Marker manifest image paths to paper-dir-relative.

Marker writes image_path relative to its -o dir; after rsync from another host
those paths (often '../something/<paper>/tables/x.png') don't resolve. We keep
only the part from the last 'tables/' or 'figures/' segment onward.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def _rebase(image_path: str) -> str:
    """Keep the path from the last 'tables/' or 'figures/' segment onward."""
    norm = image_path.replace("\\", "/")
    for anchor in ("tables/", "figures/"):
        idx = norm.rfind(anchor)
        if idx != -1:
            return norm[idx:]
    return norm


def _normalize_tables(path: Path) -> None:
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    for r in rows:
        if r.get("image_path"):
            r["image_path"] = _rebase(r["image_path"])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _normalize_figures(path: Path) -> None:
    # Marker's figures manifest carries the image path under "file" (real schema);
    # older fixtures use "image_path". Rebase whichever key is present.
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data:
        for key in ("file", "image_path"):
            if entry.get(key):
                entry[key] = _rebase(entry[key])
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize_manifests(marker_dir: Path) -> None:
    """Rewrite image_path in tables/manifest.json (CSV) and figures/manifest.json (JSON)."""
    tables = marker_dir / "tables" / "manifest.json"
    figures = marker_dir / "figures" / "manifest.json"
    if tables.is_file():
        _normalize_tables(tables)
    if figures.is_file():
        _normalize_figures(figures)
