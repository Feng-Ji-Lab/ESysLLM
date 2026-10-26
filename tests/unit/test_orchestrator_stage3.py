"""run_full applies Stage-3 derivations (fake provider, no LLM)."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from mag.orchestrator import run_full
from mag.providers.base import WireResponse
from mag.skills.loader import load_skills

SKILLS = load_skills(Path("rules"))

FIELDS_CFG = {
    "fields": [
        {
            "name": "Source of sample",
            "scope": "sample",
            "gender_specific": True,
            "type": "object",
            "items_type": "enum",
            "definition": "src",
        },
        {
            "name": "Sample",
            "scope": "sample",
            "gender_specific": True,
            "type": "object",
            "items_type": "integer",
            "definition": "n",
        },
        {
            "name": "Percentage of college or higher of participants",
            "scope": "sample",
            "gender_specific": False,
            "type": "object",
            "items_type": "number",
            "skills": ["infer_college_sample_100"],
            "definition": "pct",
        },
    ]
}


class FakeProvider:
    name = "gemini"
    model = "fake"

    def extract_section(self, *, wire_schema, system_prompt, user_prompt, assets):
        return WireResponse(
            data={
                "Source of sample": {
                    "extract_value": [{"key": "Study 1 - college sample", "value": ["college"]}],
                    "evidence_source": "x",
                    "block_id": "/page/0/Text/2",
                    "warning": "",
                },
                "Sample": {
                    "extract_value": [{"key": "Study 1 - college sample", "value": [675]}],
                    "evidence_source": "x",
                    "block_id": "/page/0/Text/2",
                    "warning": "",
                },
            },
            prompt_tokens=1,
            completion_tokens=1,
        )

    def aggregate_field(self, *, wire_schema, system_prompt, user_prompt):
        import json as _j

        if "enumerate every DISTINCT sample" in system_prompt:
            return WireResponse(
                data={
                    "samples": [
                        {"study_index": 1, "sample_label": "college sample", "total_n": 675}
                    ]
                },
                prompt_tokens=1,
                completion_tokens=1,
            )
        if "resolved_samples" not in _j.dumps(wire_schema):
            return WireResponse(
                data={"value": "None", "reasoning": "r"}, prompt_tokens=1, completion_tokens=1
            )
        if "Source of sample" in user_prompt:
            return WireResponse(
                data={
                    "resolved_samples": [
                        {
                            "sample_key": "Study 1 - college sample",
                            "values": ["college"],
                            "best_indices": [0],
                            "reasoning": "r",
                        }
                    ]
                },
                prompt_tokens=1,
                completion_tokens=1,
            )
        if "Percentage of college" in user_prompt:
            return WireResponse(data={"resolved_samples": []}, prompt_tokens=1, completion_tokens=1)
        return WireResponse(
            data={
                "resolved_samples": [
                    {
                        "sample_key": "Study 1 - college sample",
                        "values": [675],
                        "best_indices": [0],
                        "reasoning": "r",
                    }
                ]
            },
            prompt_tokens=1,
            completion_tokens=1,
        )


FIELDS_CFG_GENDER = {
    "fields": [
        {
            "name": "Source of sample",
            "scope": "sample",
            "gender_specific": True,
            "type": "object",
            "items_type": "enum",
            "definition": "src",
        },
        {
            "name": "Sample",
            "scope": "sample",
            "gender_specific": True,
            "type": "object",
            "items_type": "integer",
            "definition": "n",
            "skills": ["single_gender_fill"],
        },
    ]
}


class FakeProviderGender:
    name = "gemini"
    model = "fake"

    def extract_section(self, *, wire_schema, system_prompt, user_prompt, assets):
        return WireResponse(
            data={
                "Source of sample": {
                    "extract_value": [{"key": "Study 1 - female sample", "value": ["clinic"]}],
                    "evidence_source": "x",
                    "block_id": "/page/0/Text/2",
                    "warning": "",
                },
                "Sample": {
                    "extract_value": [{"key": "Study 1 - female sample", "value": [500]}],
                    "evidence_source": "x",
                    "block_id": "/page/0/Text/2",
                    "warning": "",
                },
            },
            prompt_tokens=1,
            completion_tokens=1,
        )

    def aggregate_field(self, *, wire_schema, system_prompt, user_prompt):
        if "enumerate every DISTINCT sample" in system_prompt:
            # Census: report a single all-female sample
            return WireResponse(
                data={
                    "samples": [
                        {
                            "study_index": 1,
                            "sample_label": "female sample",
                            "total_n": 500,
                            "gender": "all_female",
                        }
                    ]
                },
                prompt_tokens=1,
                completion_tokens=1,
            )
        if "Source of sample" in user_prompt:
            return WireResponse(
                data={
                    "resolved_samples": [
                        {
                            "sample_key": "Study 1 - female sample",
                            "values": ["clinic"],
                            "best_indices": [0],
                            "reasoning": "r",
                        }
                    ]
                },
                prompt_tokens=1,
                completion_tokens=1,
            )
        # Sample field: return a single total (length-1 → triggers single_gender_fill)
        return WireResponse(
            data={
                "resolved_samples": [
                    {
                        "sample_key": "Study 1 - female sample",
                        "values": [500],
                        "best_indices": [0],
                        "reasoning": "r",
                    }
                ]
            },
            prompt_tokens=1,
            completion_tokens=1,
        )


def test_run_full_applies_college_inference(tmp_path, prompts):
    marker_dir = tmp_path / "marker"
    shutil.copytree("tests/fixtures/marker_mini", marker_dir)
    pr = run_full(
        provider=FakeProvider(),
        marker_dir=marker_dir,
        paper_id="paper_mini",
        pdf_path="/x/paper_mini.pdf",
        fields_cfg=FIELDS_CFG,
        skills=list(SKILLS.values()),
        out_dir=tmp_path / "run",
        schema_name="bas-bmi",
        schema_version=2,
        started_at=datetime.now(UTC),
        prompts=prompts,
    )
    pct = pr.fields["Percentage of college or higher of participants"].cells[
        "Study 1 - college sample"
    ]
    assert pct.values[0].value == 100  # Stage 3 college→100 inference fired end-to-end
    assert pct.values[0].derivation.kind == "infer_constant"


def test_run_full_fires_single_gender_fill_via_census(tmp_path, prompts):
    """run_full reads sample_census.json gender and triggers single_gender_fill end-to-end."""
    marker_dir = tmp_path / "marker"
    shutil.copytree("tests/fixtures/marker_mini", marker_dir)
    pr = run_full(
        provider=FakeProviderGender(),
        marker_dir=marker_dir,
        paper_id="paper_mini",
        pdf_path="/x/paper_mini.pdf",
        fields_cfg=FIELDS_CFG_GENDER,
        skills=list(SKILLS.values()),
        out_dir=tmp_path / "run_gender",
        schema_name="bas-bmi",
        schema_version=2,
        started_at=datetime.now(UTC),
        prompts=prompts,
    )
    sample_cell = pr.fields["Sample"].cells["Study 1 - female sample"]
    # Aggregator produced [500] (total only); single_gender_fill should have expanded to
    # [total, female, male] = [500, 500, None] because the census marked it "all_female".
    assert [cv.value for cv in sample_cell.values] == [500, 500, None]
    assert sample_cell.values[1].derivation is not None
    assert sample_cell.values[1].derivation.kind == "infer_single_gender"
