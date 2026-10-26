"""Tests for the PromptPack loader."""

from __future__ import annotations

import textwrap

import pytest
from pydantic import ValidationError

from mag.prompts.loader import PromptPack, load_prompts, render

VALID_YAML = textwrap.dedent(
    """
    stage1:
      system:
        role: "You are an extraction agent."
        sample_naming: "Key by the sample name as written."
        effect_size_guidance: "Read the results text for correlations."
      user:
        section_context: "SECTION: <<SECTION_TITLE>> (<<SECTION_ID>>)"
        content: "<<SECTION_BLOCKS>>"
        assets_note: "ATTACHED <<ASSET_TYPE>> (block <<ASSET_BLOCK>>): <<ASSET_TEXT>>"
        instruction: "Extract every target field."
    stage2:
      census_system: "Enumerate every distinct sample."
      field_system: "Map each candidate onto a fixed sample key."
      flat_system: "Pick the single best paper-level value."
      gender_shape: "Output [total, female, male]."
      nongender_shape: "Output a single-element list."
    """
)


def test_load_valid_pack(tmp_path):
    (tmp_path / "prompts.yaml").write_text(VALID_YAML, encoding="utf-8")
    pack = load_prompts(tmp_path)
    assert isinstance(pack, PromptPack)
    assert pack.stage1.system.role == "You are an extraction agent."
    assert pack.stage2.gender_shape == "Output [total, female, male]."


def test_missing_required_key_raises(tmp_path):
    bad = VALID_YAML.replace('    role: "You are an extraction agent."\n', "")
    (tmp_path / "prompts.yaml").write_text(bad, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_prompts(tmp_path)


def test_unknown_key_raises(tmp_path):
    bad = VALID_YAML + "surprise: nope\n"
    (tmp_path / "prompts.yaml").write_text(bad, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_prompts(tmp_path)


def test_render_substitutes_placeholders():
    out = render("a <<X>> b <<Y>>", X="1", Y="2")
    assert out == "a 1 b 2"


def test_render_unfilled_placeholder_raises():
    with pytest.raises(KeyError):
        render("hello <<MISSING>>", X="1")


def test_load_prompts_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prompts(tmp_path)


def test_block_scalars_are_stripped(tmp_path):
    import textwrap

    yaml_text = textwrap.dedent(
        """
        stage1:
          system:
            role: |
              line one
              line two
            sample_naming: "x"
          user:
            section_context: "c"
            content: "c"
            assets_note: "c"
            instruction: "i"
        stage2:
          census_system: "c"
          field_system: "f"
          flat_system: "fl"
          gender_shape: "g"
          nongender_shape: "n"
        """
    )
    (tmp_path / "prompts.yaml").write_text(yaml_text, encoding="utf-8")
    pack = load_prompts(tmp_path)
    # no leading/trailing newline, but the internal newline between lines is kept
    assert pack.stage1.system.role == "line one\nline two"
