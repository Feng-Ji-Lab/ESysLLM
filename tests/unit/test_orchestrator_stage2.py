"""End-to-end Stage 0->2 on the mini fixture (fake provider, no LLM)."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime

from mag.models import PaperResult
from mag.orchestrator import run_full
from mag.providers.base import WireResponse

FIELDS_CFG = {
    "fields": [
        {
            "name": "Author",
            "scope": "paper",
            "gender_specific": False,
            "type": "string",
            "definition": "a",
        },
        {
            "name": "Number of studies",
            "scope": "paper",
            "gender_specific": False,
            "type": "integer",
            "definition": "n",
        },
        {
            "name": "Sample",
            "scope": "sample",
            "gender_specific": False,
            "type": "object",
            "items_type": "integer",
            "definition": "n",
        },
    ]
}


class FakeProvider:
    name = "gemini"

    def extract_section(self, *, wire_schema, system_prompt, user_prompt, assets):
        return WireResponse(
            data={
                "Author": {
                    "extract_value": "Tylka",
                    "evidence_source": "by line",
                    "block_id": "/page/0/Text/2",
                    "warning": "",
                },
                "Sample": {
                    "extract_value": [{"key": "Study 1 - college sample", "value": [675]}],
                    "evidence_source": "675",
                    "block_id": "/page/0/Text/2",
                    "warning": "",
                },
            },
            prompt_tokens=3,
            completion_tokens=2,
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
                data={"value": "Tylka", "reasoning": "r"}, prompt_tokens=1, completion_tokens=1
            )
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


def test_run_full_returns_paper_result(tmp_path, prompts):
    marker_dir = tmp_path / "marker"
    shutil.copytree("tests/fixtures/marker_mini", marker_dir)
    pr = run_full(
        provider=FakeProvider(),
        marker_dir=marker_dir,
        paper_id="paper_mini",
        pdf_path="/x/paper_mini.pdf",
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path / "run",
        schema_name="bas-bmi",
        schema_version=2,
        started_at=datetime.now(UTC),
        prompts=prompts,
    )
    assert isinstance(pr, PaperResult)
    assert pr.fields["Author"].paper_value.value == "Tylka"
    assert pr.fields["Number of studies"].paper_value.value == 1
    assert pr.fields["Sample"].cells["Study 1 - college sample"].values[0].value == 675
    assert {s.rendered for s in pr.samples} == {"Study 1 - college sample"}
    assert pr.run_meta.provider == "gemini"
    assert pr.run_meta.passes >= 1
    assert pr.run_meta.prompt_tokens > 0
    assert pr.run_meta.completion_tokens > 0
