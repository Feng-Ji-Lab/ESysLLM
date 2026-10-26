"""Tests for per-field candidate formatting."""

from __future__ import annotations

from mag.extraction.candidate_format import collect_field_candidates, format_candidates
from mag.models import EvidenceRecord, FieldCandidate


def _cand(value, gender=None, quote="q", block="/page/3/Text/5"):
    return FieldCandidate(
        field_name="Sample",
        value=value,
        value_by_gender=gender,
        evidence=[
            EvidenceRecord(
                pdf_name="p.pdf",
                section_id="003",
                block_id=block,
                page=3,
                granularity="paragraph",
                quote=quote,
            )
        ],
        warning="",
        pass_kind="text",
    )


def test_collect_skips_none_valued_candidates():
    per_section = {
        "003": {"Sample": _cand({"Study 1": [675]})},
        "004": {"Sample": _cand(None)},  # None value → skipped
        "005": {"Other": _cand({"x": [1]})},  # different field → ignored
    }
    cands = collect_field_candidates(per_section, "Sample")
    assert len(cands) == 1
    assert cands[0].value == {"Study 1": [675]}


def test_format_is_numbered_and_includes_value_and_evidence():
    cands = [_cand({"Study 1": [675]}, quote="675 (367 women, 308 men)")]
    text = format_candidates(cands)
    assert "[0]" in text
    assert "Study 1" in text
    assert "675 (367 women, 308 men)" in text
    assert "/page/3/Text/5" in text


def test_index_order_is_stable():
    cands = [_cand({"Study 1": [675]}), _cand({"Study 2": [263]})]
    text = format_candidates(cands)
    assert text.index("[0]") < text.index("[1]")


def test_includes_source_section_and_page_context():
    # section + page let the aggregator infer which study a loose candidate belongs to
    text = format_candidates([_cand({"Combined sample": [-0.27]}, quote="r=-.27")])
    assert "from=003 p3" in text


def test_format_surfaces_study_tag():
    from mag.extraction.candidate_format import format_candidates
    from mag.models import EvidenceRecord, FieldCandidate

    cand = FieldCandidate(
        field_name="Sample",
        value={"Study 1 - x": [10]},
        evidence=[
            EvidenceRecord(
                pdf_name="p.pdf",
                section_id="014",
                block_id="/page/5/Text/1",
                page=5,
                study_index=2,
                quote="q",
            )
        ],
        warning="",
        pass_kind="text",
    )
    out = format_candidates([cand])
    assert "study=2" in out
    assert "from=014 p5" in out
