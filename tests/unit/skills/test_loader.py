"""Tests for the skill loader."""

from __future__ import annotations

from pathlib import Path

from mag.skills.loader import Skill, load_skills


def _write_skill(root: Path, name: str, frontmatter: str, body: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}\n")


def test_loads_frontmatter_and_body(tmp_path):
    _write_skill(
        tmp_path,
        "study_naming",
        "name: study_naming\ndescription: how to name samples\nactivates_on: [text_pass, aggregator]",
        "Use the exact study name as written.",
    )
    skills = load_skills(tmp_path)
    s = skills["study_naming"]
    assert isinstance(s, Skill)
    assert s.name == "study_naming"
    assert s.activates_on == ["text_pass", "aggregator"]
    assert "exact study name" in s.body


def test_skips_dirs_without_skill_md(tmp_path):
    (tmp_path / "not_a_skill").mkdir()
    assert load_skills(tmp_path) == {}


def test_missing_root_returns_empty(tmp_path):
    assert load_skills(tmp_path / "nope") == {}
