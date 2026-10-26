"""Load editable Stage-1/Stage-2 prompt prose from a schema bundle's prompts.yaml.

The PromptPack holds ONLY domain-facing prose. Wire-contract instructions
(block_id verbatim, the "None" sentinel, the JSON output shape) live in code,
not here, so a prose edit cannot break parsing.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class Stage1System(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    sample_naming: str
    effect_size_guidance: str = ""


class Stage1User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_context: str
    content: str
    assets_note: str
    instruction: str


class Stage1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: Stage1System
    user: Stage1User


class Stage2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    census_system: str
    field_system: str
    flat_system: str
    gender_shape: str
    nongender_shape: str


class PromptPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage1: Stage1
    stage2: Stage2


_PLACEHOLDER = re.compile(r"<<([A-Z_]+)>>")


def render(template: str, **values: str) -> str:
    """Substitute every <<KEY>> in template; raise KeyError on an unfilled one.

    Placeholder keys must match ``[A-Z_]+`` (uppercase letters and underscores
    only).  Any ``<<...>>`` token whose inner text contains lowercase letters or
    other characters is not recognised as a placeholder and is passed through
    the template unchanged — no substitution occurs and no error is raised.
    """

    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in values:
            raise KeyError(f"unfilled placeholder <<{key}>> (have {sorted(values)})")
        return values[key]

    return _PLACEHOLDER.sub(_sub, template)


def _strip_strings(obj):
    """Recursively strip leading/trailing whitespace from every leaf string.

    YAML ``|`` block scalars retain a trailing newline; stripping here keeps
    internal newlines (multi-line guidance stays intact) while preventing
    ``\\n\\n\\n`` separators when builders ``"\\n\\n".join(...)`` prose blocks.
    """
    if isinstance(obj, dict):
        return {k: _strip_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_strings(v) for v in obj]
    if isinstance(obj, str):
        return obj.strip()
    return obj


def load_prompts(schema_dir: Path) -> PromptPack:
    """Load and validate <schema_dir>/prompts.yaml into a PromptPack."""
    data = _strip_strings(
        yaml.safe_load((Path(schema_dir) / "prompts.yaml").read_text(encoding="utf-8"))
    )
    return PromptPack.model_validate(data)
