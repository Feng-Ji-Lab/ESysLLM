"""Stage 2 — two-stage LLM aggregation into a PaperResult's fields.

2a: one sample-census call → canonical list[SampleKey].
2b: one call per field, mapping candidates onto the fixed sample list.
Paper-scope fields use a flat aggregation; "Number of studies" is derived.
All stages checkpoint to disk for idempotent reruns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from mag.extraction.aggregate_prompts import (
    build_census_prompts,
    build_field_agg_prompts,
    build_flat_agg_prompts,
)
from mag.extraction.candidate_format import collect_field_candidates, format_candidates
from mag.models import Cell, CellValue, EvidenceRecord, Field, SampleKey, Warning
from mag.providers._inflate import inflate_field_aggregation, inflate_sample_census
from mag.providers._wire import (
    build_field_aggregation_schema,
    build_flat_field_schema,
    build_sample_census_schema,
)

if TYPE_CHECKING:
    from mag.models import FieldCandidate
    from mag.prompts.loader import PromptPack
    from mag.providers.base import Provider, WireResponse
    from mag.skills.loader import Skill


def _checkpointed(path: Path, fn) -> dict:
    """Return cached JSON at path, else call fn(), cache, and return it.

    A corrupt/partial checkpoint is treated as a cache-miss and recomputed
    (matches the self-heal behavior in section_extractor.py).
    """
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass  # corrupt/partial checkpoint → recompute and overwrite
    data = fn()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def run_sample_census(
    *,
    provider: Provider,
    per_section: dict[str, dict[str, FieldCandidate]],
    skills: list[Skill],
    out_dir: Path,
    prompts: PromptPack,
) -> list[SampleKey]:
    cands = collect_field_candidates(per_section, "Sample")
    text = format_candidates(cands)
    agg_skills = [s for s in skills if "aggregator" in s.activates_on]

    def _call() -> dict:
        sysp, userp = build_census_prompts(
            sample_candidates_text=text, skills=agg_skills, prompts=prompts
        )
        resp: WireResponse = provider.aggregate_field(
            wire_schema=build_sample_census_schema(), system_prompt=sysp, user_prompt=userp
        )
        return resp.data

    raw = _checkpointed(out_dir / "sample_census.json", _call)
    return inflate_sample_census(raw)


def _evidence_for_indices(
    cands: list[FieldCandidate], best_indices: list[int]
) -> list[EvidenceRecord]:
    out = []
    for i in best_indices:
        if 0 <= i < len(cands):
            out.extend(cands[i].evidence)
    return out


def aggregate_sample_field(
    *,
    provider: Provider,
    field: dict,
    per_section: dict[str, dict[str, FieldCandidate]],
    sample_keys: list[str],
    skills: list[Skill],
    out_dir: Path,
    prompts: PromptPack,
) -> tuple[Field, list[Warning]]:
    cands = collect_field_candidates(per_section, field["name"])
    text = format_candidates(cands)
    agg_skills = [s for s in skills if "aggregator" in s.activates_on]

    def _call() -> dict:
        sysp, userp = build_field_agg_prompts(
            field=field,
            sample_keys=sample_keys,
            candidates_text=text,
            skills=agg_skills,
            prompts=prompts,
        )
        resp: WireResponse = provider.aggregate_field(
            wire_schema=build_field_aggregation_schema(field, sample_keys),
            system_prompt=sysp,
            user_prompt=userp,
        )
        return resp.data

    raw = _checkpointed(out_dir / "aggregated" / f"{field['name']}.json", _call)
    mapping = inflate_field_aggregation(raw, field)
    resolved = raw.get("resolved_samples", [])
    ev_by_key = {
        s["sample_key"]: _evidence_for_indices(cands, s.get("best_indices", [])) for s in resolved
    }
    cells: dict[str, Cell] = {}
    for key, values in mapping.items():
        evidence = ev_by_key.get(key, [])
        cells[key] = Cell(values=[CellValue(value=v, evidence=evidence) for v in values])

    # Safety net: a candidate Stage-1 extracted a real value for, but whose value never
    # made it into any resolved cell, was dropped — surface it. Redundant duplicates are
    # suppressed: a candidate value-list is "represented" if it matches a resolved cell
    # exactly, or is a single total equal to a resolved cell's total (position 0). Only
    # genuinely-unrepresented values warn (e.g. a sample mislabelled with the wrong study).
    resolved_lists = [tuple(s.get("values") or []) for s in resolved]
    resolved_set = {t for t in resolved_lists if t}
    resolved_totals = {t[0] for t in resolved_lists if t}

    def _represented(vlist: list) -> bool:
        t = tuple(vlist)
        return t in resolved_set or (len(t) == 1 and t[0] in resolved_totals)

    def _dropped_value_lists(value: object) -> list:
        if isinstance(value, dict):
            lists = [v for v in value.values() if isinstance(v, list)]
        elif isinstance(value, list):
            lists = [value]
        else:
            return []
        # An empty value-list carries no real value, so it can't be "dropped" — skip it.
        return [v for v in lists if v and not _represented(v)]

    warnings: list[Warning] = []
    for i, cand in enumerate(cands):
        dropped = _dropped_value_lists(cand.value)
        if dropped:
            ev = cand.evidence[0] if cand.evidence else None
            src = ev.section_id if ev else "?"
            warnings.append(
                Warning(
                    code="unmapped_candidate",
                    field_name=field["name"],
                    message=(
                        f"candidate [{i}] from {src} carries value(s) {dropped} not placed "
                        "in any sample"
                    ),
                )
            )

    field_obj = Field(
        name=field["name"],
        scope="sample",
        gender_specific=field.get("gender_specific", False),
        cells=cells,
    )
    return field_obj, warnings


def aggregate_paper_field(
    *,
    provider: Provider,
    field: dict,
    per_section: dict[str, dict[str, FieldCandidate]],
    skills: list[Skill],
    out_dir: Path,
    prompts: PromptPack,
) -> Field:
    cands = collect_field_candidates(per_section, field["name"])
    text = format_candidates(cands)
    agg_skills = [s for s in skills if "aggregator" in s.activates_on]

    def _call() -> dict:
        sysp, userp = build_flat_agg_prompts(
            field=field, candidates_text=text, skills=agg_skills, prompts=prompts
        )
        resp: WireResponse = provider.aggregate_field(
            wire_schema=build_flat_field_schema(field), system_prompt=sysp, user_prompt=userp
        )
        return resp.data

    raw = _checkpointed(out_dir / "aggregated" / f"{field['name']}.json", _call)
    value = raw.get("value")
    if value == "None":
        value = None
    evidence = cands[0].evidence if cands else []
    return Field(
        name=field["name"],
        scope="paper",
        paper_value=CellValue(value=value, evidence=evidence),
    )


def assemble_paper_result(
    *,
    provider: Provider,
    per_section: dict[str, dict[str, FieldCandidate]],
    fields_cfg: dict,
    skills: list[Skill],
    out_dir: Path,
    prompts: PromptPack,
) -> tuple[dict[str, Field], list[SampleKey], list[Warning]]:
    """Run Stage 2a + 2b and build {field_name: Field}, the sample list, and warnings."""
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = run_sample_census(
        provider=provider, per_section=per_section, skills=skills, out_dir=out_dir, prompts=prompts
    )
    sample_keys = [s.rendered for s in samples]
    n_studies = len({s.study_index for s in samples})

    fields: dict[str, Field] = {}
    warnings: list[Warning] = []
    for f in fields_cfg["fields"]:
        name = f["name"]
        if f["scope"] == "paper":
            if name == "Number of studies":
                fields[name] = Field(
                    name=name, scope="paper", paper_value=CellValue(value=n_studies)
                )
            else:
                fields[name] = aggregate_paper_field(
                    provider=provider,
                    field=f,
                    per_section=per_section,
                    skills=skills,
                    out_dir=out_dir,
                    prompts=prompts,
                )
        else:
            fields[name], field_warnings = aggregate_sample_field(
                provider=provider,
                field=f,
                per_section=per_section,
                sample_keys=sample_keys,
                skills=skills,
                out_dir=out_dir,
                prompts=prompts,
            )
            warnings.extend(field_warnings)
    if not samples:
        warnings.append(Warning(code="no_samples", message="sample census returned no samples"))
    return fields, samples, warnings
