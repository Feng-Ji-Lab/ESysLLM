"""Pure functions converting wire JSON into internal models. No LLM, no IO.

These are the inverse of the wire schemas in _wire.py and are 100% unit-testable
with canned responses. The provider impls call these after a raw LLM call.
"""

from __future__ import annotations

import re
from typing import Any

from mag.models import EvidenceRecord, FieldCandidate, SampleKey
from mag.providers._wire import restore_pairs

# The census LLM sometimes folds a "Study N -" prefix into the sample_label
# (e.g. "Study 2 - college students"). SampleKey.rendered adds that prefix
# itself, so strip a leading "Study <n> <sep>" to avoid "Study 2 - Study 2 - ...".
_STUDY_PREFIX = re.compile(r"^\s*study\s+\d+\s*[-–—:]\s*", re.IGNORECASE)  # noqa: RUF001


def _normalize_block_id(block_id: str | None) -> str | None:
    """Strip a copied [bracket] prefix and repair a missing leading slash."""
    if not block_id:
        return None
    b = block_id.strip().strip("[]").strip()
    if b.startswith("page/"):
        b = "/" + b
    return b or None


def _page_from_block(block_id: str | None) -> int | None:
    """Parse the page index out of a Marker block id like '/page/3/Text/7'."""
    if not block_id:
        return None
    parts = block_id.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "page" and parts[1].isdigit():
        return int(parts[1])
    return None


def inflate_section_response(
    *,
    raw: dict,
    section_id: str,
    section_title: str,
    pass_kind: str,
    pdf_name: str,
    fields_cfg: dict,
    study_index: int | None = None,
) -> dict[str, FieldCandidate]:
    """Wire {field: {extract_value, evidence_source, block_id, warning, ...}} →
    {field_name: FieldCandidate} with [{key,value}] arrays restored and evidence built."""
    out: dict[str, FieldCandidate] = {}
    for f in fields_cfg["fields"]:
        name = f["name"]
        node = raw.get(name)
        if not isinstance(node, dict):
            continue

        ev_src = node.get("evidence_source", "") or ""
        block_id = _normalize_block_id(node.get("block_id"))
        evidence: list[EvidenceRecord] = []
        if ev_src or block_id:
            evidence.append(
                EvidenceRecord(
                    pdf_name=pdf_name,
                    section_id=section_id,
                    section_title=section_title,
                    block_id=block_id,
                    page=_page_from_block(block_id),
                    study_index=study_index,
                    granularity="paragraph",
                    quote=ev_src,
                )
            )

        # Dormant since R2: build_section_schema no longer emits
        # extract_value_by_gender (gender is positional in the value list,
        # [total, female, male]). Kept tolerant in case a schema/provider
        # re-introduces a gender object; normally `by_gender` stays None.
        by_gender_raw = node.get("extract_value_by_gender")
        by_gender: dict[str, Any] | None = None
        if isinstance(by_gender_raw, dict):
            by_gender = {g: restore_pairs(v) for g, v in by_gender_raw.items()}

        out[name] = FieldCandidate(
            field_name=name,
            value=restore_pairs(node.get("extract_value")),
            value_by_gender=by_gender,
            evidence=evidence,
            warning=node.get("warning", "") or "",
            pass_kind="asset" if pass_kind == "asset" else "text",
        )
    return out


def inflate_sample_census(raw: dict) -> list[SampleKey]:
    """Wire {samples: [{study_index, sample_label, total_n, ...}]} → list[SampleKey].

    Strips a redundant leading "Study N -" the census LLM sometimes folds into the
    label, so SampleKey.rendered doesn't double the prefix.
    """
    out: list[SampleKey] = []
    for s in raw.get("samples", []):
        label = _STUDY_PREFIX.sub("", str(s.get("sample_label", ""))).strip()
        out.append(SampleKey(study_index=int(s["study_index"]), sample_label=label))
    return out


def inflate_census_gender(raw: dict) -> dict[str, str]:
    """Wire census → {rendered_sample_key: gender} for single-gender samples only.

    Mirrors inflate_sample_census's label normalization so keys match SampleKey.rendered.
    Only "all_female"/"all_male" are kept; "mixed"/absent are omitted.
    """
    out: dict[str, str] = {}
    for s in raw.get("samples", []):
        g = s.get("gender")
        if g not in ("all_female", "all_male"):
            continue
        label = _STUDY_PREFIX.sub("", str(s.get("sample_label", ""))).strip()
        key = SampleKey(study_index=int(s["study_index"]), sample_label=label).rendered
        out[key] = g
    return out


def inflate_field_aggregation(raw: dict, field: dict) -> dict[str, list]:
    """Wire {resolved_samples: [{sample_key, values, ...}]} → {sample_key: values}.

    Stage R1 returns the raw mapping; R3 builds the full Field (Cells + evidence
    linking via best_indices against the candidate list).
    """
    return {s["sample_key"]: list(s.get("values", [])) for s in raw.get("resolved_samples", [])}
