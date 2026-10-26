"""Aggregator tests with a scripted fake provider (no LLM)."""

from __future__ import annotations

from mag.extraction.aggregator import assemble_paper_result
from mag.models import EvidenceRecord, FieldCandidate
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
            "gender_specific": True,
            "position_order": ["total", "female", "male"],
            "type": "object",
            "items_type": "integer",
            "definition": "n",
        },
    ]
}


def _cand(field, value, quote="q"):
    return FieldCandidate(
        field_name=field,
        value=value,
        evidence=[
            EvidenceRecord(
                pdf_name="p.pdf",
                section_id="003",
                block_id="/page/3/Text/5",
                page=3,
                granularity="paragraph",
                quote=quote,
            )
        ],
        warning="",
        pass_kind="text",
    )


class ScriptedProvider:
    """Returns census, then a flat 'Author' answer, then a 'Sample' field answer."""

    name = "scripted"

    def __init__(self):
        self.census = {
            "samples": [
                {"study_index": 1, "sample_label": "college sample", "total_n": 675},
                {"study_index": 2, "sample_label": "community sample", "total_n": 317},
            ]
        }
        self.flat = {"value": "Tylka", "reasoning": "author line"}
        self.field = {
            "resolved_samples": [
                {
                    "sample_key": "Study 1 - college sample",
                    "values": [675, 367, 308],
                    "best_indices": [0],
                    "reasoning": "r",
                },
                {
                    "sample_key": "Study 2 - community sample",
                    "values": [317, 150, 167],
                    "best_indices": [0],
                    "reasoning": "r",
                },
            ]
        }

    def aggregate_field(self, *, wire_schema, system_prompt, user_prompt):
        import json

        if "enumerate every DISTINCT sample" in system_prompt:
            return WireResponse(data=self.census, prompt_tokens=1, completion_tokens=1)
        if '"value"' in json.dumps(wire_schema) and "resolved_samples" not in json.dumps(
            wire_schema
        ):
            return WireResponse(data=self.flat, prompt_tokens=1, completion_tokens=1)
        return WireResponse(data=self.field, prompt_tokens=1, completion_tokens=1)

    def extract_section(self, **k):
        raise NotImplementedError


def _per_section():
    return {
        "003": {
            "Author": _cand("Author", "Tylka"),
            "Sample": _cand(
                "Sample", {"Study 1 - college sample": [675]}, quote="675 (367 women, 308 men)"
            ),
        }
    }


def test_assemble_builds_samples_and_number_of_studies(tmp_path, prompts):
    pr_fields, samples, _warnings = assemble_paper_result(
        provider=ScriptedProvider(),
        per_section=_per_section(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    rendered = {s.rendered for s in samples}
    assert rendered == {"Study 1 - college sample", "Study 2 - community sample"}
    assert pr_fields["Number of studies"].paper_value.value == 2


def test_paper_field_resolved_flat(tmp_path, prompts):
    pr_fields, _, _ = assemble_paper_result(
        provider=ScriptedProvider(),
        per_section=_per_section(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert pr_fields["Author"].scope == "paper"
    assert pr_fields["Author"].paper_value.value == "Tylka"


def test_sample_field_cells_positional_and_evidence(tmp_path, prompts):
    pr_fields, _, _ = assemble_paper_result(
        provider=ScriptedProvider(),
        per_section=_per_section(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    sample = pr_fields["Sample"]
    assert sample.scope == "sample"
    cell = sample.cells["Study 1 - college sample"]
    assert [cv.value for cv in cell.values] == [675, 367, 308]
    assert cell.values[0].evidence and cell.values[0].evidence[0].block_id == "/page/3/Text/5"


def test_checkpoints_written(tmp_path, prompts):
    assemble_paper_result(
        provider=ScriptedProvider(),
        per_section=_per_section(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert (tmp_path / "sample_census.json").is_file()
    assert (tmp_path / "aggregated" / "Sample.json").is_file()


def test_rerun_uses_checkpoints(tmp_path, prompts):
    prov = ScriptedProvider()
    assemble_paper_result(
        provider=prov,
        per_section=_per_section(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    prov.aggregate_field = lambda **k: (_ for _ in ()).throw(
        AssertionError("should not call provider")
    )
    pr_fields, samples, _ = assemble_paper_result(
        provider=prov,
        per_section=_per_section(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert {s.rendered for s in samples} == {
        "Study 1 - college sample",
        "Study 2 - community sample",
    }
    assert pr_fields["Sample"].cells["Study 2 - community sample"].values[0].value == 317


def test_empty_census_emits_warning(tmp_path, prompts):
    class EmptyCensusProvider(ScriptedProvider):
        def __init__(self):
            super().__init__()
            self.census = {"samples": []}
            self.field = {"resolved_samples": []}

    pr_fields, samples, warnings = assemble_paper_result(
        provider=EmptyCensusProvider(),
        per_section=_per_section(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert samples == []
    assert any(w.code == "no_samples" for w in warnings)
    assert pr_fields["Number of studies"].paper_value.value == 0
    assert pr_fields["Sample"].cells == {}


def test_unmapped_candidate_emits_warning(tmp_path, prompts):
    # Two Sample candidates; the (scripted) aggregator cites only index 0 (best_indices=[0]),
    # so index 1 was extracted but never placed → must surface, not silently drop.
    per_section = {
        "003": {"Sample": _cand("Sample", {"Study 1 - college sample": [675]}, quote="675")},
        "012": {"Sample": _cand("Sample", {"Combined sample": [999]}, quote="combined 999")},
    }
    _fields, _samples, warnings = assemble_paper_result(
        provider=ScriptedProvider(),
        per_section=per_section,
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    unmapped = [w for w in warnings if w.code == "unmapped_candidate"]
    assert len(unmapped) == 1
    assert unmapped[0].field_name == "Sample"
    assert "[1]" in unmapped[0].message


def test_empty_value_list_does_not_warn(tmp_path, prompts):
    # A candidate carrying an empty value-list holds no real value → must NOT warn.
    per_section = {
        "003": {"Sample": _cand("Sample", {"Study 1 - college sample": [675]}, quote="675")},
        "012": {"Sample": _cand("Sample", {"Study 9 - phantom": []}, quote="no number")},
    }
    _fields, _samples, warnings = assemble_paper_result(
        provider=ScriptedProvider(),
        per_section=per_section,
        fields_cfg=FIELDS_CFG,
        skills=[],
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert [w for w in warnings if w.code == "unmapped_candidate"] == []
