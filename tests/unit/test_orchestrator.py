"""Stage 0 + Stage 1 orchestration on the mini fixture (fake provider)."""

from __future__ import annotations

import shutil

from mag.orchestrator import run_stage01
from mag.providers.base import WireResponse

FIELDS_CFG = {
    "fields": [
        {
            "name": "Sample",
            "scope": "sample",
            "gender_specific": False,
            "type": "object",
            "items_type": "integer",
            "definition": "n",
        }
    ]
}


class FakeProvider:
    name = "fake"

    def extract_section(self, *, wire_schema, system_prompt, user_prompt, assets):
        return WireResponse(
            data={
                "Sample": {
                    "extract_value": [{"key": "Study 1", "value": [675]}],
                    "evidence_source": "675",
                    "block_id": "/page/0/Text/2",
                    "warning": "",
                }
            },
            prompt_tokens=1,
            completion_tokens=1,
        )

    def aggregate_field(self, *, wire_schema, system_prompt, user_prompt):
        raise NotImplementedError


def test_run_stage01_builds_sections_and_extracts(tmp_path, prompts):
    marker_dir = tmp_path / "marker"
    shutil.copytree("tests/fixtures/marker_mini", marker_dir)
    out_dir = tmp_path / "run"
    result = run_stage01(
        provider=FakeProvider(),
        marker_dir=marker_dir,
        paper_id="paper_mini",
        fields_cfg=FIELDS_CFG,
        skills=[],
        pdf_name="paper_mini.pdf",
        out_dir=out_dir,
        prompts=prompts,
    )
    assert any("Sample" in fields for fields in result.values())
    assert list((out_dir / "sections").glob("*__text.json"))
