"""Prompt builders for Stage 2a (sample census) and Stage 2b (per-field aggregation).

Editable prose comes from the bundle's PromptPack; the only code-owned text is the
"None" sentinel rule (wire contract) appended to the flat (paper-level) prompt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mag.prompts.loader import PromptPack
    from mag.skills.loader import Skill

# Code-owned wire contract for the paper-level field.
_NONE_SENTINEL_RULE = 'Return the string "None" only if no candidate reports it.'


def _skill_text(skills: list[Skill], field_name: str | None = None) -> str:
    chosen = [
        s
        for s in skills
        if not s.applies_to or (field_name is not None and field_name in s.applies_to)
    ]
    return "\n\n".join(f"RULE {s.name}: {s.body}" for s in chosen)


def build_census_prompts(
    *, sample_candidates_text: str, skills: list[Skill], prompts: PromptPack
) -> tuple[str, str]:
    system = "\n\n".join(p for p in (prompts.stage2.census_system, _skill_text(skills)) if p)
    user = "Candidate sample descriptions (from the paper's sections):\n\n" + sample_candidates_text
    return system, user


def build_field_agg_prompts(
    *,
    field: dict,
    sample_keys: list[str],
    candidates_text: str,
    skills: list[Skill],
    prompts: PromptPack,
) -> tuple[str, str]:
    shape = (
        prompts.stage2.gender_shape
        if field.get("gender_specific")
        else prompts.stage2.nongender_shape
    )
    system = "\n\n".join(
        p
        for p in (
            prompts.stage2.field_system,
            f"FIELD DEFINITION: {field.get('definition', '')}",
            shape,
            _skill_text(skills, field.get("name")),
        )
        if p
    )
    keys = "\n".join(f"- {k}" for k in sample_keys)
    user = (
        f"FIELD: {field['name']}\n\nKNOWN SAMPLE KEYS (use exactly these):\n{keys}\n\n"
        f"CANDIDATES:\n{candidates_text}\n\nConsolidate into resolved_samples."
    )
    return system, user


def build_flat_agg_prompts(
    *, field: dict, candidates_text: str, skills: list[Skill], prompts: PromptPack
) -> tuple[str, str]:
    system = "\n\n".join(
        p
        for p in (
            prompts.stage2.flat_system,
            _NONE_SENTINEL_RULE,
            f"FIELD DEFINITION: {field.get('definition', '')}",
            _skill_text(skills, field.get("name")),
        )
        if p
    )
    user = (
        f"FIELD: {field['name']}\n\nCANDIDATES:\n{candidates_text}\n\nReturn the single best value."
    )
    return system, user
