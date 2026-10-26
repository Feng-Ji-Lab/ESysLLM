"""Tests for Stage-1 prompt construction."""

from __future__ import annotations

from pathlib import Path

from mag.extraction.prompt_builder import build_section_prompts
from mag.preprocessing.section_builder import Asset, Block, Section
from mag.skills.loader import Skill

FIELDS_CFG = {
    "fields": [
        {
            "name": "Sample",
            "scope": "sample",
            "gender_specific": True,
            "type": "object",
            "items_type": "integer",
            "definition": "participants [total, female, male]",
        },
    ]
}

SKILLS = [Skill(name="study_naming", activates_on=["text_pass"], body="Name samples exactly.")]


def _section() -> Section:
    return Section(
        section_id="003_participants",
        section_title="Participants",
        text="A total of 675 ...",
        blocks=[
            Block(block_id="/page/3/Text/5", page=3, text="A total of 675 (367 women, 308 men).")
        ],
    )


def test_user_prompt_prefixes_blocks_with_block_id(prompts):
    _sysp, userp = build_section_prompts(
        section=_section(), fields_cfg=FIELDS_CFG, skills=SKILLS, asset=None, prompts=prompts
    )
    assert "[/page/3/Text/5]" in userp
    assert "675" in userp


def test_system_prompt_injects_field_definitions_and_skill_body(prompts):
    sysp, _ = build_section_prompts(
        section=_section(), fields_cfg=FIELDS_CFG, skills=SKILLS, asset=None, prompts=prompts
    )
    assert "participants [total, female, male]" in sysp
    assert "Name samples exactly." in sysp
    assert "block_id" in sysp.lower()  # evidence policy mentions block_id
    assert "EFFECT SIZE" in sysp  # effect_size_guidance prose wired through


def test_asset_pass_mentions_attached_asset_caption_and_note(prompts):
    asset = Asset(
        block_id="/page/6/Table/0",
        type="table",
        page=6,
        path=Path("/x/t0.png"),
        caption="Table 1",
        note="Note. Study 1: N = 675.",
    )
    _, userp = build_section_prompts(
        section=_section(), fields_cfg=FIELDS_CFG, skills=SKILLS, asset=asset, prompts=prompts
    )
    assert "Table 1" in userp
    assert "N = 675" in userp  # note text included


def test_no_asset_omits_attachment_line(prompts):
    _, userp = build_section_prompts(
        section=_section(), fields_cfg=FIELDS_CFG, skills=SKILLS, asset=None, prompts=prompts
    )
    assert "ATTACHED" not in userp
