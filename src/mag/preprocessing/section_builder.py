"""Turn a Marker output directory into in-memory Sections + Assets.

Cleaner rewrite of the v1 `preprocessor.py`; kept its output structure but
flattened the logic.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Block:
    block_id: str
    page: int
    text: str


@dataclass
class Asset:
    block_id: str
    type: str  # "table" | "figure"
    page: int
    path: Path
    caption: str | None = None
    note: str | None = None
    bbox: list[float] | None = None


@dataclass
class Section:
    section_id: str
    section_title: str
    text: str
    study_index: int = 1
    blocks: list[Block] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)


def build_sections(marker_dir: Path, paper_id: str) -> list[Section]:
    doc = json.loads((marker_dir / f"{paper_id}.json").read_text(encoding="utf-8"))
    figures = _load_figures_manifest(marker_dir)
    tables = _load_tables_manifest(marker_dir)

    id_to_text: dict[str, str] = {}
    _index_block_texts(doc, id_to_text)

    sections: dict[str, Section] = {}
    counter = 0
    current_study = 1
    table_ord: dict[int, int] = {}   # per-page count of Table blocks seen
    figure_ord: dict[int, int] = {}  # per-page count of Picture blocks seen

    def _walk(node: dict) -> None:
        nonlocal counter, current_study
        btype = node.get("block_type")
        if btype == "Page":
            for child in node.get("children") or []:
                _walk(child)
            return
        if btype in ("PageHeader", "PageFooter"):
            return
        if btype in ("TableGroup", "FigureGroup"):
            for child in node.get("children") or []:
                _walk(child)
            return

        hierarchy = node.get("section_hierarchy") or {}
        if hierarchy:
            s = _study_index_from_hierarchy(hierarchy, id_to_text)
            if s is not None:
                current_study = s
        hdr_id: str | None = None
        if hierarchy:
            deepest = sorted(hierarchy.keys(), key=int)[-1]
            hdr_id = hierarchy[deepest]

        if hdr_id and hdr_id not in sections:
            counter += 1
            title = _strip_html(id_to_text.get(hdr_id, "Unknown Section"))
            base = _safe_id(title) or f"section_{counter}"
            sec_id = f"{counter:03d}_{base}"
            sections[hdr_id] = Section(
                section_id=sec_id, section_title=title, text="", study_index=current_study
            )

        sec_key = hdr_id or "__front__"
        if sec_key not in sections:
            counter += 1
            sections[sec_key] = Section(
                section_id=f"{counter:03d}_front_matter",
                section_title="Front matter",
                text="",
                study_index=current_study,
            )
        sec = sections[sec_key]

        if btype in ("Text", "ListItem"):
            text = _strip_html(node.get("html", ""))
            if text:
                page = _page_of(node.get("id", ""))
                sec.blocks.append(Block(block_id=node.get("id", ""), page=page, text=text))
        elif btype == "Table":
            pg = _page_of(node.get("id", ""))
            ordn = table_ord.get(pg, 0)
            table_ord[pg] = ordn + 1
            _attach_asset(
                sec, node, tables, asset_type="table", marker_dir=marker_dir,
                id_to_text=id_to_text, ordinal=ordn, index_field="table_index",
            )
        elif btype in ("Picture", "Figure"):
            # Marker emits both "Picture" and "Figure" block types for images
            # (the latter often inside a FigureGroup, e.g. a correlation matrix
            # saved as a figure). Both must attach a figure asset.
            pg = _page_of(node.get("id", ""))
            ordn = figure_ord.get(pg, 0)
            figure_ord[pg] = ordn + 1
            _attach_asset(
                sec, node, figures, asset_type="figure", marker_dir=marker_dir,
                id_to_text=id_to_text, ordinal=ordn, index_field="index",
            )

    for page in doc.get("children", []):
        _walk(page)

    for sec in sections.values():
        sec.text = "\n".join(b.text for b in sec.blocks)

    return list(sections.values())


def _attach_asset(
    sec: Section,
    node: dict,
    manifest: list[dict],
    *,
    asset_type: str,
    marker_dir: Path,
    id_to_text: dict[str, str] | None = None,
    ordinal: int | None = None,
    index_field: str | None = None,
) -> None:
    block_id = node.get("id", "")
    page = _page_of(block_id)

    def _page_match(m: dict) -> bool:
        return m.get("page_index") == str(page) or m.get("page_index") == page

    # 1) exact block_id; 2) same page AND the Nth asset of this type on the page
    # (use the per-page ordinal so multiple figures/tables on one page map to the
    # right image, not all to the first); 3) fall back to first on the page.
    entry = next((m for m in manifest if m.get("block_id") == block_id), None)
    if entry is None and ordinal is not None and index_field:
        entry = next(
            (m for m in manifest if _page_match(m) and str(m.get(index_field)) == str(ordinal)),
            None,
        )
    if entry is None:
        entry = next((m for m in manifest if _page_match(m)), None)
    if entry is None or not entry.get("image_path"):
        return
    img_path = Path(entry["image_path"])
    if not img_path.is_absolute():
        img_path = marker_dir / img_path

    # Resolve caption and note from block IDs when an id_to_text index is available
    # (tables manifest stores caption_block_id / note_block_id; figures manifest may
    # store the text directly or omit it).
    caption = entry.get("caption")
    note = entry.get("note")
    if id_to_text:
        caption_bid = entry.get("caption_block_id")
        if caption_bid and caption_bid not in ("", "nan", None):
            caption = _strip_html(id_to_text.get(str(caption_bid), caption or "")) or caption
        note_bid = entry.get("note_block_id")
        if note_bid and note_bid not in ("", "nan", None):
            note = _strip_html(id_to_text.get(str(note_bid), note or "")) or note

    sec.assets.append(
        Asset(
            block_id=block_id,
            type=asset_type,
            page=page,
            path=img_path.resolve(),
            caption=caption,
            note=note,
        )
    )


def _index_block_texts(node: dict, out: dict[str, str]) -> None:
    if isinstance(node, dict):
        if "id" in node and node.get("html"):
            out[node["id"]] = node["html"]
        for child in node.get("children") or []:
            _index_block_texts(child, out)


def _rebase_asset_path(p: str) -> str:
    """Keep a manifest image path from the last 'figures/'|'tables/' segment on,
    so a remote/absolute path (e.g. Marker's -o dir on another host) resolves
    under the local marker_dir. Mirrors manifest_normalizer._rebase."""
    norm = str(p).replace("\\", "/")
    for anchor in ("figures/", "tables/"):
        idx = norm.rfind(anchor)
        if idx != -1:
            return norm[idx:]
    return norm


def _load_figures_manifest(marker_dir: Path) -> list[dict]:
    """Load figures/manifest.json and NORMALIZE its schema.

    The figures manifest uses keys ``file`` / ``page`` / ``index`` (and may carry
    an absolute remote path), whereas ``_attach_asset`` matches on ``page_index``
    and reads ``image_path``. Map the keys and rebase the path so figure images
    actually attach (Marker often saves correlation matrices as figures).
    """
    path = marker_dir / "figures" / "manifest.json"
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict] = []
    for entry in raw:
        e = dict(entry)
        if not e.get("image_path"):
            img = e.get("file") or e.get("image_path")
            if img:
                e["image_path"] = _rebase_asset_path(img)
        if e.get("page_index") is None and e.get("page") is not None:
            e["page_index"] = e["page"]
        out.append(e)
    return out


def _load_tables_manifest(marker_dir: Path) -> list[dict]:
    path = marker_dir / "tables" / "manifest.json"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _page_of(block_id: str) -> int:
    parts = block_id.split("/")
    try:
        if len(parts) > 2 and parts[1] == "page":
            return int(parts[2])
    except ValueError:
        pass
    return 0


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


_STUDY_HEADING = re.compile(r"(?i)\b(?:study|experiment)\s+(\d+)\b")


def _study_index_from_hierarchy(hierarchy: dict, id_to_text: dict[str, str]) -> int | None:
    """Return the study number from any heading in a block's section_hierarchy.

    Scans hierarchy levels shallow→deep; the deepest match wins. None if no
    "Study N" or "Experiment N" heading is present.
    """
    found: int | None = None
    for _level, hid in sorted(hierarchy.items(), key=lambda kv: int(kv[0])):
        m = _STUDY_HEADING.search(_strip_html(id_to_text.get(hid, "")))
        if m:
            found = int(m.group(1))
    return found


def _safe_id(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s]", "", text.lower())
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:50]
