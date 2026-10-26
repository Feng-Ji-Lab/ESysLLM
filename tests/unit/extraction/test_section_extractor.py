"""Stage-1 section extractor with checkpointing (fake provider, no LLM)."""

from __future__ import annotations

from mag.extraction.section_extractor import extract_paper_sections
from mag.preprocessing.section_builder import Block, Section
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

    def __init__(self):
        self.calls = 0

    def extract_section(self, *, wire_schema, system_prompt, user_prompt, assets):
        self.calls += 1
        return WireResponse(
            data={
                "Sample": {
                    "extract_value": [{"key": "Study 1", "value": [675]}],
                    "evidence_source": "675",
                    "block_id": "/page/3/Text/5",
                    "warning": "",
                }
            },
            prompt_tokens=5,
            completion_tokens=4,
        )

    def aggregate_field(self, *, wire_schema, system_prompt, user_prompt):  # unused here
        raise NotImplementedError


def _sections():
    return [
        Section(
            section_id="003_participants",
            section_title="Participants",
            text="675",
            blocks=[Block(block_id="/page/3/Text/5", page=3, text="675 ...")],
        )
    ]


def test_writes_checkpoint_and_returns_candidates(tmp_path, prompts):
    prov = FakeProvider()
    cands, toks, _warnings = extract_paper_sections(
        provider=prov,
        sections=_sections(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        pdf_name="p.pdf",
        out_dir=tmp_path,
        prompts=prompts,
    )
    ckpt = tmp_path / "sections" / "003_participants__text.json"
    assert ckpt.is_file()
    assert prov.calls == 1
    assert cands["003_participants"]["Sample"].value == {"Study 1": [675]}
    assert toks == (5, 4)


def test_rerun_skips_completed_pass(tmp_path, prompts):
    prov = FakeProvider()
    extract_paper_sections(
        provider=prov,
        sections=_sections(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        pdf_name="p.pdf",
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert prov.calls == 1
    cands, _, _warnings = extract_paper_sections(
        provider=prov,
        sections=_sections(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        pdf_name="p.pdf",
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert prov.calls == 1
    assert cands["003_participants"]["Sample"].value == {"Study 1": [675]}


def test_malformed_checkpoint_recovers(tmp_path, prompts):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True)
    (sec_dir / "003_participants__text.json").write_text("{ not json")  # corrupt
    prov = FakeProvider()
    cands, _, _warnings = extract_paper_sections(
        provider=prov,
        sections=_sections(),
        fields_cfg=FIELDS_CFG,
        skills=[],
        pdf_name="p.pdf",
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert prov.calls == 1  # re-extracted despite the bad checkpoint
    assert cands["003_participants"]["Sample"].value == {"Study 1": [675]}


def test_asset_pass_runs_and_checkpoints(tmp_path, prompts):
    from mag.preprocessing.section_builder import Asset

    png = tmp_path / "t0.png"
    png.write_bytes(b"PNG")
    sec = Section(
        section_id="006_results",
        section_title="Results",
        text="r",
        blocks=[Block(block_id="/page/6/Text/4", page=6, text="Table 1 ...")],
        assets=[
            Asset(block_id="/page/6/Table/0", type="table", page=6, path=png, caption="Table 1")
        ],
    )
    prov = FakeProvider()
    extract_paper_sections(
        provider=prov,
        sections=[sec],
        fields_cfg=FIELDS_CFG,
        skills=[],
        pdf_name="p.pdf",
        out_dir=tmp_path,
        prompts=prompts,
    )
    assert (tmp_path / "sections" / "006_results__asset_0.json").is_file()
    assert prov.calls == 2  # text pass + one asset pass


def test_ungrounded_text_candidate_is_dropped_and_warned(tmp_path, prompts):
    from mag.extraction.section_extractor import extract_paper_sections
    from mag.preprocessing.section_builder import Block, Section
    from mag.providers.base import WireResponse

    section = Section(
        section_id="009_method",
        section_title="Method",
        text="Participants were 660 women from Kuala Lumpur, Malaysia.",
        blocks=[
            Block(
                block_id="/page/2/Text/3",
                page=2,
                text="Participants were 660 women from Kuala Lumpur, Malaysia.",
            )
        ],
    )

    class FabProvider:
        name = "fab"

        def extract_section(self, *, wire_schema, system_prompt, user_prompt, assets):
            return WireResponse(
                data={
                    "Sample": {
                        "extract_value": [{"key": "Study 1 - undergraduates", "value": [200]}],
                        "evidence_source": "200 undergraduate students from the southeastern United States",
                        "block_id": "009_method",
                    }
                },
                prompt_tokens=1,
                completion_tokens=1,
            )

        def aggregate_field(self, **k):
            raise NotImplementedError

    fields_cfg = {"fields": [{"name": "Sample", "scope": "sample", "type": "object"}]}
    per_section, _tok, warnings = extract_paper_sections(
        provider=FabProvider(),
        sections=[section],
        fields_cfg=fields_cfg,
        skills=[],
        pdf_name="p.pdf",
        out_dir=tmp_path,
        prompts=prompts,
    )

    assert "Sample" not in per_section.get("009_method", {})  # dropped
    assert any(w.code == "ungrounded_candidate" for w in warnings)


def test_grounded_text_candidate_is_kept(tmp_path, prompts):
    from mag.extraction.section_extractor import extract_paper_sections
    from mag.preprocessing.section_builder import Block, Section
    from mag.providers.base import WireResponse

    section = Section(
        section_id="011_method",
        section_title="Method",
        text="A total of 675 participants (367 women, 308 men) were analyzed.",
        blocks=[
            Block(
                block_id="/page/3/Text/5",
                page=3,
                text="A total of 675 participants (367 women, 308 men) were analyzed.",
            )
        ],
    )

    class GoodProvider:
        name = "good"

        def extract_section(self, *, wire_schema, system_prompt, user_prompt, assets):
            return WireResponse(
                data={
                    "Sample": {
                        "extract_value": [{"key": "Study 1", "value": [675]}],
                        "evidence_source": "A total of 675 participants (367 women, 308 men)",
                        "block_id": "/page/3/Text/5",
                    }
                },
                prompt_tokens=1,
                completion_tokens=1,
            )

        def aggregate_field(self, **k):
            raise NotImplementedError

    fields_cfg = {"fields": [{"name": "Sample", "scope": "sample", "type": "object"}]}
    per_section, _tok, warnings = extract_paper_sections(
        provider=GoodProvider(),
        sections=[section],
        fields_cfg=fields_cfg,
        skills=[],
        pdf_name="p.pdf",
        out_dir=tmp_path,
        prompts=prompts,
    )

    assert "Sample" in per_section["011_method"]  # kept
    assert not [w for w in warnings if w.code == "ungrounded_candidate"]
