"""Stage 3 driver: run skill executors (value-changing) then validators (read-only)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from mag.derive.registry import EXECUTORS, VALIDATORS

if TYPE_CHECKING:
    from mag.models import Field, Warning
    from mag.skills.loader import Skill


def run_derivations(
    *,
    fields: dict[str, Field],
    fields_cfg: dict,
    skills: dict[str, Skill],
    context: dict | None = None,
) -> tuple[dict[str, Field], list[Warning]]:
    """Return (updated fields, warnings). Executors run before validators."""
    out = dict(fields)

    for f in fields_cfg["fields"]:
        if f["name"] not in out:
            continue
        for skill_name in f.get("skills", []):
            skill = skills.get(skill_name)
            if skill is None or not skill.executor:
                continue
            fn = EXECUTORS.get(skill.executor)
            if fn is None:
                raise KeyError(f"skill {skill.name!r} declares unknown executor {skill.executor!r}")
            out[f["name"]] = fn(fields=out, target=f["name"], skill=skill, context=context)

    warnings: list[Warning] = []
    # Validators read their own target field internally, so this pass does not
    # gate on f["name"] being present in `out` (unlike the executor pass).
    for f in fields_cfg["fields"]:
        for skill_name in f.get("skills", []):
            skill = skills.get(skill_name)
            if skill is None or not skill.validator:
                continue
            fn = VALIDATORS.get(skill.validator)
            if fn is None:
                raise KeyError(
                    f"skill {skill.name!r} declares unknown validator {skill.validator!r}"
                )
            warnings.extend(fn(fields=out, skill=skill))
    return out, warnings
