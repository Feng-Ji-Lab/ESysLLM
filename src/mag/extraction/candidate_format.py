"""Format per-section field candidates for an aggregation prompt.

`collect_field_candidates` returns the ordered list (index i == [i] in the
prompt) so the LLM's best_indices map back to candidates (and their evidence).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mag.models import FieldCandidate


def collect_field_candidates(
    per_section: dict[str, dict[str, FieldCandidate]], field_name: str
) -> list[FieldCandidate]:
    """Non-None candidates for one field, prioritizing asset-derived ones.

    Marker writes asset blocks (figures / tables / CONSORT diagrams) into
    `<section>__asset_<i>` keys. These are the cleanest source of cell-level
    integers (Table 1, CONSORT randomization boxes) and we want the LLM
    aggregator to see them FIRST so they show up at low candidate indices
    where the model is most likely to attend. Within each tier we keep
    stable section-id order so reasoning remains deterministic.
    """
    asset_cands: list[FieldCandidate] = []
    text_cands: list[FieldCandidate] = []
    for _section_id in sorted(per_section):
        cand = per_section[_section_id].get(field_name)
        if cand is None or cand.value is None:
            continue
        if "__asset" in _section_id:
            asset_cands.append(cand)
        else:
            text_cands.append(cand)
    return asset_cands + text_cands


def format_candidates(candidates: list[FieldCandidate]) -> str:
    """Numbered candidate block for the user prompt."""
    lines: list[str] = []
    for i, c in enumerate(candidates):
        value = json.dumps(c.value, ensure_ascii=False)
        parts = [f"[{i}] value={value}"]
        if c.value_by_gender:
            parts.append(f"by_gender={json.dumps(c.value_by_gender, ensure_ascii=False)}")
        ev = c.evidence[0] if c.evidence else None
        if ev:
            # section + page give the aggregator study context (an earlier
            # section / lower page number is an earlier study) so it can place a
            # loosely-labelled candidate like "Combined sample".
            src = ev.section_id or ""
            if ev.page is not None:
                src = f"{src} p{ev.page}".strip()
            if src:
                parts.append(f"from={src}")
            if ev.study_index is not None:
                parts.append(f"study={ev.study_index}")
            parts.append(f"evidence=({ev.block_id}) {ev.quote!r}")
        lines.append(" ".join(parts))
    return "\n".join(lines)
