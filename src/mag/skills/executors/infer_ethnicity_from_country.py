"""Executor: infer predominant ethnicity from the sample's country when unreported.

Mirrors the meta-analysts' own coding convention (Buecker 2023 gold infers a
predominant ethnicity from country for ethnically-homogeneous samples). Runs in the
derive stage, so it can read the resolved `country` field — which the per-field
aggregator cannot. Only fills ethnicity when it is missing / "not specified"; a
reported composition (adopted at aggregation) is left untouched.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from mag.models import CellValue, Derivation

if TYPE_CHECKING:
    from mag.models import Field
    from mag.skills.loader import Skill

# European / European-heritage countries → predominantly white/european.
# (USA / Canada deliberately excluded — genuinely multi-ethnic; leave to reported data.)
_WHITE = {
    "germany", "unitedkingdom", "uk", "england", "scotland", "wales", "sweden",
    "netherlands", "finland", "norway", "denmark", "poland", "switzerland", "austria",
    "belgium", "france", "italy", "spain", "portugal", "ireland", "czechrepublic",
    "hungary", "greece", "romania", "slovenia", "slovakia", "croatia", "estonia",
    "lithuania", "latvia", "iceland", "luxembourg", "australia", "newzealand",
}
_ASIAN = {"china", "japan", "korea", "southkorea", "taiwan", "hongkong", "singapore"}


def _norm(s) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower()) if s is not None else ""


def infer_ethnicity_from_country(
    *, fields: dict[str, Field], target: str, skill: Skill, context: dict | None = None
) -> Field:
    eth = fields[target]
    cur = eth.paper_value.value if eth.paper_value else None
    # only infer when ethnicity was not reported / left "not specified"
    if cur not in (None, "None", "", "not specified"):
        return eth
    country = fields.get("country")
    cn = _norm(country.paper_value.value) if country and country.paper_value else ""
    mapped = None
    if any(k in cn for k in _WHITE):
        mapped = "predominantly white/european"
    elif any(k in cn for k in _ASIAN):
        mapped = "predominantly asian"
    if mapped is None:
        return eth
    return eth.model_copy(update={
        "paper_value": CellValue(
            value=mapped,
            derivation=Derivation(
                kind="infer_constant",
                skill_name=skill.name,
                inputs={"country": country.paper_value.value if country and country.paper_value else None},
                note="predominant ethnicity inferred from country (unreported in paper)",
            ),
            confidence=0.5,
        )
    })
