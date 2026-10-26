"""Stage 1 — per-section extraction with idempotent (section, pass) checkpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from mag.extraction.grounding import is_grounded
from mag.extraction.prompt_builder import build_section_prompts
from mag.models import Warning
from mag.providers._inflate import inflate_section_response
from mag.providers._wire import build_section_schema
from mag.providers.base import Asset as WireAsset

if TYPE_CHECKING:
    from mag.models import FieldCandidate
    from mag.preprocessing.section_builder import Section
    from mag.prompts.loader import PromptPack
    from mag.providers.base import Provider, WireResponse
    from mag.skills.loader import Skill


def _read_asset_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def extract_paper_sections(
    *,
    provider: Provider,
    sections: list[Section],
    fields_cfg: dict,
    skills: list[Skill],
    pdf_name: str,
    out_dir: Path,
    prompts: PromptPack,
) -> tuple[dict[str, dict[str, FieldCandidate]], tuple[int, int], list[Warning]]:
    """Run text + per-asset passes for every section.

    Returns ({section_id: {field_name: FieldCandidate}}, (prompt_tokens, completion_tokens),
    warnings). Each (section, pass) is checkpointed to out_dir/sections/<section_id>__<pass>.json
    and reused on rerun. Text-pass candidates whose evidence quote is not grounded in the
    section text are dropped (a hallucination signal) and surfaced as warnings.
    """
    wire_schema = build_section_schema(fields_cfg)
    ckpt_dir = out_dir / "sections"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    text_skills = [s for s in skills if "text_pass" in s.activates_on]
    asset_skills = [s for s in skills if "asset_pass" in s.activates_on]

    per_section: dict[str, dict[str, FieldCandidate]] = {}
    prompt_tok = 0
    completion_tok = 0
    warnings: list[Warning] = []

    for sec in sections:
        merged: dict[str, FieldCandidate] = {}
        passes: list[tuple[str, object, list[Skill]]] = [("text", None, text_skills)]
        for i, asset in enumerate(sec.assets):
            passes.append((f"asset_{i}", asset, asset_skills))

        for pass_name, asset, active in passes:
            ckpt = ckpt_dir / f"{sec.section_id}__{pass_name}.json"
            raw = None
            if ckpt.is_file():
                try:
                    raw = json.loads(ckpt.read_text(encoding="utf-8"))["data"]
                except (json.JSONDecodeError, KeyError, OSError):
                    raw = None  # corrupt/partial checkpoint → re-extract and overwrite
            if raw is None:
                sysp, userp = build_section_prompts(
                    section=sec, fields_cfg=fields_cfg, skills=active, asset=asset, prompts=prompts
                )
                wire_assets: list[WireAsset] = []
                if asset is not None:
                    data = _read_asset_bytes(asset.path)
                    if data:
                        mime = "image/png" if str(asset.path).endswith(".png") else "image/jpeg"
                        wire_assets.append(
                            WireAsset(path=str(asset.path), mime_type=mime, data=data)
                        )
                resp: WireResponse = provider.extract_section(
                    wire_schema=wire_schema,
                    system_prompt=sysp,
                    user_prompt=userp,
                    assets=wire_assets,
                )
                raw = resp.data
                prompt_tok += resp.prompt_tokens
                completion_tok += resp.completion_tokens
                ckpt.write_text(
                    json.dumps(
                        {
                            "prompt_tokens": resp.prompt_tokens,
                            "completion_tokens": resp.completion_tokens,
                            "data": raw,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            kind = "asset" if pass_name.startswith("asset") else "text"
            cands = inflate_section_response(
                raw=raw,
                section_id=sec.section_id,
                study_index=sec.study_index,
                section_title=sec.section_title,
                pass_kind=kind,
                pdf_name=pdf_name,
                fields_cfg=fields_cfg,
            )
            # Anti-hallucination grounding (text passes only; asset values come from
            # the table image, not section text, so they cannot be quote-checked).
            if kind == "text":
                sec_text = " ".join(b.text for b in sec.blocks) or sec.text
                for name in list(cands):
                    cand = cands[name]
                    # "Number of studies" is a paper-level count, not a verbatim
                    # sentence, so it has no groundable quote — exempt it.
                    if name == "Number of studies":
                        continue
                    # `cand.value` uses the v1 "None" string sentinel for "not found".
                    has_value = cand.value not in (None, "None") and cand.value != []
                    quote = cand.evidence[0].quote if cand.evidence else ""
                    if has_value and not is_grounded(quote, sec_text):
                        warnings.append(
                            Warning(
                                code="ungrounded_candidate",
                                field_name=name,
                                message=(
                                    f"{sec.section_id}/{name}: quote not found in section "
                                    f"(likely hallucinated): {quote[:80]!r}"
                                ),
                            )
                        )
                        del cands[name]
            for name, cand in cands.items():
                if name not in merged or cand.value is not None or cand.value_by_gender is not None:
                    merged[name] = cand
        per_section[sec.section_id] = merged

    return per_section, (prompt_tok, completion_tok), warnings
