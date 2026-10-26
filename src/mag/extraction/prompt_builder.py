"""Build the Stage-1 system + user prompts for one section pass.

Editable prose comes from the bundle's prompts.yaml (PromptPack); the wire
contract (block_id-verbatim emission, the "None" sentinel, the JSON field
definitions) stays here in code so a prose edit cannot break parsing.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from mag.prompts.loader import render

if TYPE_CHECKING:
    from mag.preprocessing.section_builder import Asset, Section
    from mag.prompts.loader import PromptPack
    from mag.skills.loader import Skill

# Code-owned wire contract — never moved to YAML.
_EVIDENCE_POLICY = (
    "Every value must include evidence: copy the EXACT block_id (verbatim, from the "
    "[brackets] prefixing each paragraph) of the block the value came from, plus a short "
    "quote in evidence_source. If a field is not reported in this section, return the "
    'string "None" — never guess.'
)


def build_section_prompts(
    *,
    section: Section,
    fields_cfg: dict,
    skills: list[Skill],
    asset: Asset | None,
    prompts: PromptPack,
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for one section pass."""
    s1 = prompts.stage1
    defs = [
        {k: f[k] for k in ("name", "type", "items_type", "allowed_values", "definition") if k in f}
        for f in fields_cfg["fields"]
    ]
    skill_text = "\n\n".join(f"RULE {s.name}: {s.body}" for s in skills)
    system = "\n\n".join(
        part
        for part in (
            s1.system.role,
            s1.system.sample_naming,
            s1.system.effect_size_guidance,
            _EVIDENCE_POLICY,
            "FIELD DEFINITIONS:\n" + json.dumps(defs, ensure_ascii=False),
            skill_text,
        )
        if part
    )

    block_lines = "\n".join(f"[{b.block_id}] {b.text}" for b in section.blocks) or section.text
    user_parts = [
        render(
            s1.user.section_context,
            SECTION_TITLE=section.section_title,
            SECTION_ID=section.section_id,
        ),
        render(s1.user.content, SECTION_BLOCKS=block_lines),
    ]
    if asset is not None:
        extra = " ".join(p for p in (asset.caption or "", asset.note or "") if p)
        user_parts.append(
            render(
                s1.user.assets_note,
                ASSET_TYPE=asset.type.upper(),
                ASSET_BLOCK=asset.block_id,
                ASSET_TEXT=extra,
            ).rstrip()
        )
    user_parts.append(s1.user.instruction)
    return system, "\n\n".join(user_parts)
