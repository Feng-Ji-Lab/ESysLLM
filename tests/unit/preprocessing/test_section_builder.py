"""Tests for the Marker→Section builder."""

from __future__ import annotations

import json
from pathlib import Path

from mag.preprocessing.section_builder import Asset, Block, build_sections

MINI = Path("tests/fixtures/marker_mini")


def test_builds_one_section_with_title():
    secs = build_sections(MINI, "paper_mini")
    titled = [s for s in secs if s.section_title == "Participants"]
    assert len(titled) == 1
    assert titled[0].section_id.endswith("_participants")


def test_section_collects_text_block_with_id_and_page():
    sec = next(s for s in build_sections(MINI, "paper_mini") if s.section_title == "Participants")
    assert any(
        isinstance(b, Block) and b.block_id == "/page/0/Text/2" and b.page == 0 for b in sec.blocks
    )
    assert "675" in sec.text


def test_table_asset_attached_with_resolved_path_and_caption():
    sec = next(s for s in build_sections(MINI, "paper_mini") if s.section_title == "Participants")
    tables = [a for a in sec.assets if a.type == "table"]
    assert len(tables) == 1
    a: Asset = tables[0]
    assert a.type == "table"
    assert a.path.name == "t0.png"
    assert a.path.is_absolute()
    # caption resolved from the caption block id -> the Text/2 html
    assert a.caption and "675" in a.caption


def test_figure_asset_attached_with_resolved_path():
    """Figures manifest uses file/page/index keys (not image_path/page_index);
    the builder must still attach the figure image and rebase its remote path."""
    sec = next(s for s in build_sections(MINI, "paper_mini") if s.section_title == "Participants")
    figs = [a for a in sec.assets if a.type == "figure"]
    assert len(figs) == 1
    a = figs[0]
    assert a.path.name == "f0.png"
    assert a.path.is_absolute()
    assert a.path == (MINI / "figures" / "f0.png").resolve()
    assert a.caption and "scatterplot" in a.caption.lower()


def test_single_study_paper_tags_all_sections_study_1():
    secs = build_sections(MINI, "paper_mini")
    assert secs and all(s.study_index == 1 for s in secs)


def test_two_figures_on_one_page_attach_distinctly(tmp_path):
    """Two Picture blocks on the same page must map to DISTINCT figure images by
    per-page index, not both to the first figure (the residual bug: a correlation
    matrix bundled in the 2nd figure on a page was being dropped)."""
    doc = {
        "block_type": "Document",
        "children": [
            {
                "block_type": "Page",
                "id": "/page/0/Page/0",
                "children": [
                    {
                        "block_type": "SectionHeader", "id": "/page/0/SectionHeader/0",
                        "html": "<h1>Results</h1>",
                        "section_hierarchy": {"1": "/page/0/SectionHeader/0"},
                    },
                    {"block_type": "Picture", "id": "/page/0/Picture/1",
                     "section_hierarchy": {"1": "/page/0/SectionHeader/0"}},
                    # second image is a "Figure" block (Marker uses both types;
                    # the matrix-bearing image is often a Figure, not a Picture)
                    {"block_type": "Figure", "id": "/page/0/Figure/2",
                     "section_hierarchy": {"1": "/page/0/SectionHeader/0"}},
                ],
            }
        ],
    }
    (tmp_path / "p.json").write_text(json.dumps(doc), encoding="utf-8")
    figdir = tmp_path / "figures"
    figdir.mkdir()
    for name in ("f0.png", "f1.png"):
        (figdir / name).write_bytes(b"\x89PNG\r\n\x1a\n")
    (figdir / "manifest.json").write_text(json.dumps([
        {"page": 0, "index": 0, "file": "/remote/p/figures/f0.png"},
        {"page": 0, "index": 1, "file": "/remote/p/figures/f1.png"},
    ]))
    secs = build_sections(tmp_path, "p")
    fig_names = sorted(a.path.name for s in secs for a in s.assets if a.type == "figure")
    assert fig_names == ["f0.png", "f1.png"]  # both, distinct — not ["f0.png","f0.png"]


def test_study_heading_advances_study_index(tmp_path):
    # Page 0: Study 1 content; Page 1: a "Study 2" header (level 1) with a "Method"
    # sub-header (level 2) and a text block under both → that section is study 2.
    doc = {
        "block_type": "Document",
        "children": [
            {
                "block_type": "Page",
                "id": "/page/0/Page/0",
                "children": [
                    {
                        "block_type": "SectionHeader",
                        "id": "/page/0/SectionHeader/0",
                        "html": "<h1>Study 1</h1>",
                        "section_hierarchy": {"1": "/page/0/SectionHeader/0"},
                    },
                    {
                        "block_type": "Text",
                        "id": "/page/0/Text/1",
                        "html": "<p>S1 method.</p>",
                        "section_hierarchy": {"1": "/page/0/SectionHeader/0"},
                    },
                ],
            },
            {
                "block_type": "Page",
                "id": "/page/1/Page/0",
                "children": [
                    {
                        "block_type": "SectionHeader",
                        "id": "/page/1/SectionHeader/0",
                        "html": "<h1>Study 2</h1>",
                        "section_hierarchy": {"1": "/page/1/SectionHeader/0"},
                    },
                    {
                        "block_type": "SectionHeader",
                        "id": "/page/1/SectionHeader/1",
                        "html": "<h2>Method</h2>",
                        "section_hierarchy": {
                            "1": "/page/1/SectionHeader/0",
                            "2": "/page/1/SectionHeader/1",
                        },
                    },
                    {
                        "block_type": "Text",
                        "id": "/page/1/Text/2",
                        "html": "<p>S2 method, 165 women.</p>",
                        "section_hierarchy": {
                            "1": "/page/1/SectionHeader/0",
                            "2": "/page/1/SectionHeader/1",
                        },
                    },
                ],
            },
        ],
    }
    (tmp_path / "p.json").write_text(json.dumps(doc), encoding="utf-8")
    secs = build_sections(tmp_path, "p")
    by_study = {s.study_index for s in secs if "165 women" in s.text}
    assert by_study == {2}  # the Study-2 Method section is tagged 2
    assert any(s.study_index == 1 and "S1 method" in s.text for s in secs)  # Study-1 stays 1


def test_sample_subheading_does_not_advance_study(tmp_path):
    # A "Sample 2 characteristics" demographics sub-heading must NOT bump the study index.
    doc = {
        "block_type": "Document",
        "children": [
            {
                "block_type": "Page",
                "id": "/page/0/Page/0",
                "children": [
                    {
                        "block_type": "SectionHeader",
                        "id": "/page/0/SectionHeader/0",
                        "html": "<h1>Sample 2 characteristics</h1>",
                        "section_hierarchy": {"1": "/page/0/SectionHeader/0"},
                    },
                    {
                        "block_type": "Text",
                        "id": "/page/0/Text/1",
                        "html": "<p>demographics here</p>",
                        "section_hierarchy": {"1": "/page/0/SectionHeader/0"},
                    },
                ],
            },
        ],
    }
    (tmp_path / "p.json").write_text(json.dumps(doc), encoding="utf-8")
    secs = build_sections(tmp_path, "p")
    assert all(s.study_index == 1 for s in secs)
