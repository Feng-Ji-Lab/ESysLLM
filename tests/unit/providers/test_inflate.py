"""Tests for wire→internal inflation (pure functions, no LLM)."""

from __future__ import annotations

from mag.models import SampleKey
from mag.providers._inflate import (
    _page_from_block,
    inflate_field_aggregation,
    inflate_sample_census,
    inflate_section_response,
)

FIELDS_CFG = {
    "fields": [
        {"name": "Author", "scope": "paper", "type": "string"},
        {
            "name": "Sample",
            "scope": "sample",
            "gender_specific": True,
            "type": "object",
            "items_type": "integer",
        },
    ]
}


def test_page_from_block():
    assert _page_from_block("/page/3/Text/7") == 3
    assert _page_from_block("/page/0/Picture/1") == 0
    assert _page_from_block(None) is None
    assert _page_from_block("garbage") is None


def test_inflate_section_restores_pairs_and_evidence():
    raw = {
        "Author": {
            "extract_value": "Tylka",
            "evidence_source": "author line on p1",
            "block_id": "/page/0/Text/2",
            "warning": "",
        },
        "Sample": {
            "extract_value": [{"key": "Study 1", "value": [675]}],
            "extract_value_by_gender": {
                "female": [{"key": "Study 1", "value": [367]}],
                "male": [{"key": "Study 1", "value": [308]}],
                "total": "None",
                "other": "None",
            },
            "evidence_source": "675 (367 women and 308 men)",
            "block_id": "/page/3/Text/5",
            "warning": "",
        },
    }
    cands = inflate_section_response(
        raw=raw,
        section_id="003_participants",
        section_title="Participants",
        pass_kind="text",
        pdf_name="1Tylka2015.pdf",
        fields_cfg=FIELDS_CFG,
    )
    assert cands["Author"].value == "Tylka"
    assert cands["Author"].evidence[0].block_id == "/page/0/Text/2"
    assert cands["Author"].evidence[0].page == 0
    assert cands["Sample"].value == {"Study 1": [675]}
    assert cands["Sample"].value_by_gender["female"] == {"Study 1": [367]}
    assert cands["Sample"].value_by_gender["total"] is None
    assert cands["Sample"].evidence[0].page == 3
    assert cands["Sample"].pass_kind == "text"


def test_inflate_section_skips_missing_fields():
    raw = {"Author": {"extract_value": "X", "evidence_source": "", "block_id": "", "warning": ""}}
    cands = inflate_section_response(
        raw=raw,
        section_id="001",
        section_title="",
        pass_kind="text",
        pdf_name="p.pdf",
        fields_cfg=FIELDS_CFG,
    )
    assert "Author" in cands
    assert "Sample" not in cands  # not present in raw


def test_inflate_section_no_evidence_when_blank():
    raw = {"Author": {"extract_value": "X", "evidence_source": "", "block_id": "", "warning": ""}}
    cands = inflate_section_response(
        raw=raw,
        section_id="001",
        section_title="",
        pass_kind="text",
        pdf_name="p.pdf",
        fields_cfg=FIELDS_CFG,
    )
    assert cands["Author"].evidence == []


def test_inflate_sample_census():
    raw = {
        "samples": [
            {"study_index": 1, "sample_label": "college students", "total_n": 675},
            {"study_index": 1, "sample_label": "test-retest subsample", "total_n": 208},
            {"study_index": 2, "sample_label": "MTurk community participants", "total_n": 317},
        ]
    }
    keys = inflate_sample_census(raw)
    assert keys[0] == SampleKey(study_index=1, sample_label="college students")
    assert keys[0].rendered == "Study 1 - college students"
    assert len(keys) == 3


def test_inflate_sample_census_strips_redundant_study_prefix():
    raw = {
        "samples": [
            {"study_index": 2, "sample_label": "Study 2 - college students", "total_n": 263},
            {"study_index": 3, "sample_label": "Study 3 - MTurk community sample", "total_n": 382},
            {"study_index": 1, "sample_label": "675 participants", "total_n": 675},
        ]
    }
    keys = inflate_sample_census(raw)
    # the redundant "Study N -" prefix is stripped so rendered keys aren't doubled
    assert keys[0].sample_label == "college students"
    assert keys[0].rendered == "Study 2 - college students"
    assert keys[1].rendered == "Study 3 - MTurk community sample"
    # a non-prefixed label is left untouched
    assert keys[2].rendered == "Study 1 - 675 participants"


def test_inflate_field_aggregation_maps_keys_to_values():
    raw = {
        "resolved_samples": [
            {
                "sample_key": "Study 1 - college students",
                "values": [675, 367, 308],
                "best_indices": [0],
                "reasoning": "r",
            },
            {
                "sample_key": "Study 2 - MTurk community participants",
                "values": [317, 150, 167],
                "best_indices": [1],
                "reasoning": "r",
            },
        ]
    }
    mapping = inflate_field_aggregation(raw, {"type": "object", "items_type": "integer"})
    assert mapping["Study 1 - college students"] == [675, 367, 308]
    assert mapping["Study 2 - MTurk community participants"] == [317, 150, 167]


def test_inflate_section_value_by_gender_none_when_absent():
    raw = {
        "Sample": {
            "extract_value": [{"key": "Study 1", "value": [675]}],
            "evidence_source": "x",
            "block_id": "/page/3/Text/5",
            "warning": "",
        }
    }
    cands = inflate_section_response(
        raw=raw,
        section_id="003",
        section_title="P",
        pass_kind="text",
        pdf_name="p.pdf",
        fields_cfg=FIELDS_CFG,
    )
    assert cands["Sample"].value_by_gender is None


def test_inflate_section_asset_pass_kind():
    raw = {"Author": {"extract_value": "X", "evidence_source": "e", "block_id": "", "warning": ""}}
    cands = inflate_section_response(
        raw=raw,
        section_id="001",
        section_title="",
        pass_kind="asset",
        pdf_name="p.pdf",
        fields_cfg=FIELDS_CFG,
    )
    assert cands["Author"].pass_kind == "asset"


def test_inflate_missing_keys_yield_empty():
    assert inflate_sample_census({}) == []
    assert inflate_field_aggregation({}, {"type": "object"}) == {}


def test_inflate_census_gender_maps_rendered_key_to_gender():
    from mag.providers._inflate import inflate_census_gender

    raw = {
        "samples": [
            {
                "study_index": 1,
                "sample_label": "US sample",
                "total_n": 8925,
                "gender": "all_female",
            },
            {
                "study_index": 1,
                "sample_label": "Study 1 - mixed group",
                "total_n": 100,
                "gender": "mixed",
            },
            {"study_index": 2, "sample_label": "men only", "total_n": 50, "gender": "all_male"},
        ]
    }
    m = inflate_census_gender(raw)
    assert m["Study 1 - US sample"] == "all_female"
    assert m["Study 2 - men only"] == "all_male"
    assert "Study 1 - mixed group" not in m  # only single-gender kept


def test_inflate_normalizes_block_id_brackets_and_slash():
    from mag.providers._inflate import inflate_section_response

    fields_cfg = {"fields": [{"name": "Sample", "type": "object"}]}
    raw = {
        "Sample": {
            "extract_value": [{"key": "Study 1", "value": [675]}],
            "evidence_source": "675 participants",
            "block_id": "[/page/3/Text/5]",  # bracket-wrapped
        }
    }
    out = inflate_section_response(
        raw=raw,
        section_id="003",
        section_title="M",
        pass_kind="text",
        pdf_name="p.pdf",
        fields_cfg=fields_cfg,
    )
    ev = out["Sample"].evidence[0]
    assert ev.block_id == "/page/3/Text/5"  # brackets stripped
    assert ev.page == 3  # page parses after normalization


def test_inflate_normalizes_block_id_missing_slash():
    from mag.providers._inflate import inflate_section_response

    fields_cfg = {"fields": [{"name": "Sample", "type": "object"}]}
    raw = {
        "Sample": {
            "extract_value": [{"key": "S", "value": [10]}],
            "evidence_source": "x",
            "block_id": "page/2/Text/1",
        }
    }
    out = inflate_section_response(
        raw=raw,
        section_id="002",
        section_title="M",
        pass_kind="text",
        pdf_name="p.pdf",
        fields_cfg=fields_cfg,
    )
    assert out["Sample"].evidence[0].block_id == "/page/2/Text/1"
    assert out["Sample"].evidence[0].page == 2


def test_inflate_sets_study_index_on_evidence():
    from mag.providers._inflate import inflate_section_response

    fields_cfg = {"fields": [{"name": "Sample", "type": "object"}]}
    raw = {
        "Sample": {
            "extract_value": [{"key": "S", "value": [10]}],
            "evidence_source": "x",
            "block_id": "/page/5/Text/1",
        }
    }
    out = inflate_section_response(
        raw=raw,
        section_id="014",
        section_title="Method",
        pass_kind="text",
        pdf_name="p.pdf",
        fields_cfg=fields_cfg,
        study_index=2,
    )
    assert out["Sample"].evidence[0].study_index == 2
