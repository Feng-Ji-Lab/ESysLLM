"""Pipeline orchestration. R2 covers Stage 0 (ingest) + Stage 1 (section extraction)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from mag.derive.runner import run_derivations
from mag.extraction.aggregator import assemble_paper_result
from mag.extraction.section_extractor import extract_paper_sections
from mag.models import PaperResult, RunMeta
from mag.preprocessing.manifest_normalizer import normalize_manifests
from mag.preprocessing.section_builder import build_sections
from mag.providers._inflate import inflate_census_gender

if TYPE_CHECKING:
    from mag.models import FieldCandidate
    from mag.prompts.loader import PromptPack
    from mag.providers.base import Provider
    from mag.skills.loader import Skill


def run_stage01(
    *,
    provider: Provider,
    marker_dir: Path,
    paper_id: str,
    fields_cfg: dict,
    skills: list[Skill],
    pdf_name: str,
    out_dir: Path,
    prompts: PromptPack,
) -> dict[str, dict[str, FieldCandidate]]:
    """Stage 0 (normalize manifests + build sections) then Stage 1 (extract).

    Returns {section_id: {field_name: FieldCandidate}}. Checkpoints land under
    out_dir/sections/. Stage-1 grounding warnings are discarded here; use
    run_full to collect them on the PaperResult.
    """
    normalize_manifests(marker_dir)
    sections = build_sections(marker_dir, paper_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_section, _tokens, _warnings = extract_paper_sections(
        provider=provider,
        sections=sections,
        fields_cfg=fields_cfg,
        skills=skills,
        pdf_name=pdf_name,
        out_dir=out_dir,
        prompts=prompts,
    )
    return per_section


def run_stage2(
    *,
    provider: Provider,
    per_section: dict[str, dict[str, FieldCandidate]],
    fields_cfg: dict,
    skills: list[Skill],
    out_dir: Path,
    prompts: PromptPack,
):
    """Stage 2 only: returns (fields, samples, warnings)."""
    return assemble_paper_result(
        provider=provider,
        per_section=per_section,
        fields_cfg=fields_cfg,
        skills=skills,
        out_dir=out_dir,
        prompts=prompts,
    )


def run_full(
    *,
    provider: Provider,
    marker_dir: Path,
    paper_id: str,
    pdf_path: str,
    fields_cfg: dict,
    skills: list[Skill],
    out_dir: Path,
    schema_name: str,
    schema_version: int,
    started_at: datetime,
    prompts: PromptPack,
) -> PaperResult:
    """Stage 0 -> 1 -> 2, returning a complete PaperResult."""
    normalize_manifests(marker_dir)
    sections = build_sections(marker_dir, paper_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_section, (ptok, ctok), stage1_warnings = extract_paper_sections(
        provider=provider,
        sections=sections,
        fields_cfg=fields_cfg,
        skills=skills,
        pdf_name=Path(pdf_path).name,
        out_dir=out_dir,
        prompts=prompts,
    )
    fields, samples, warnings = assemble_paper_result(
        provider=provider,
        per_section=per_section,
        fields_cfg=fields_cfg,
        skills=skills,
        out_dir=out_dir,
        prompts=prompts,
    )
    census_path = out_dir / "sample_census.json"
    gender_ctx: dict[str, dict[str, str]] = {}
    if census_path.is_file():
        try:
            gender_ctx = {
                "sample_gender": inflate_census_gender(
                    json.loads(census_path.read_text(encoding="utf-8"))
                )
            }
        except (json.JSONDecodeError, OSError):
            gender_ctx = {}
    # inject this paper's publication year (for schema skills that estimate from it,
    # e.g. yearT1 = pub_year - 3 - span). Store lives at schemas/<schema>/publication_years.json.
    try:
        py_path = Path(__file__).resolve().parents[2] / "schemas" / schema_name / "publication_years.json"
        if py_path.is_file():
            py = json.loads(py_path.read_text(encoding="utf-8")).get(paper_id)
            if py is not None:
                gender_ctx["publication_year"] = py
    except (json.JSONDecodeError, OSError):
        pass
    skills_by_name = {s.name: s for s in skills}
    fields, derive_warnings = run_derivations(
        fields=fields, fields_cfg=fields_cfg, skills=skills_by_name, context=gender_ctx
    )
    warnings = stage1_warnings + warnings + derive_warnings
    return PaperResult(
        paper_id=paper_id,
        pdf_path=pdf_path,
        marker_output_dir=str(marker_dir),
        samples=samples,
        fields=fields,
        warnings=warnings,
        run_meta=RunMeta(
            run_id=out_dir.name,
            provider=provider.name,  # type: ignore[arg-type]
            model=getattr(provider, "model", "unknown"),
            schema_name=schema_name,
            schema_version=schema_version,
            skill_names=[s.name for s in skills],
            started_at=started_at,
            finished_at=datetime.now(UTC),
            prompt_tokens=ptok,
            completion_tokens=ctok,
            passes=sum(len(v) for v in per_section.values()),
            aggregator_passes=len(fields_cfg["fields"]),
        ),
    )
