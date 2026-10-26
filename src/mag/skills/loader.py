"""Load rule Skills from rules/<name>/SKILL.md (frontmatter + Markdown body).

Our 'Skills' are not a provider feature — the body is injected into the prompt as
text. Executor/validator resolution arrives in R4.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict
from pydantic import Field as PField


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    activates_on: list[str] = PField(default_factory=list)
    executor: str | None = None
    validator: str | None = None
    applies_to: list[str] = PField(default_factory=list)
    body: str = ""
    extras: dict = PField(default_factory=dict)


def _parse(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body.strip()
    return {}, text.strip()


def load_skills(root: Path) -> dict[str, Skill]:
    """Return {skill_name: Skill} for every rules/<name>/SKILL.md under root."""
    out: dict[str, Skill] = {}
    if not root.is_dir():
        return out
    known = {"name", "description", "activates_on", "executor", "validator", "applies_to"}
    for d in sorted(root.iterdir()):
        md = d / "SKILL.md"
        if not md.is_file():
            continue
        fm, body = _parse(md.read_text(encoding="utf-8"))
        out[fm.get("name", d.name)] = Skill(
            name=fm.get("name", d.name),
            description=fm.get("description", ""),
            activates_on=fm.get("activates_on", []),
            executor=fm.get("executor"),
            validator=fm.get("validator"),
            applies_to=fm.get("applies_to", []),
            body=body,
            extras={k: v for k, v in fm.items() if k not in known},
        )
    return out
