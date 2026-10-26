"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_batch_dir(tmp_path: Path) -> Path:
    """A per-test batch directory matching the runtime layout."""
    (tmp_path / "pdf").mkdir()
    (tmp_path / "marker").mkdir()
    (tmp_path / "extractions").mkdir()
    return tmp_path


@pytest.fixture
def prompts():
    """The shipped bas-bmi PromptPack, for builder/orchestrator tests."""
    from mag.prompts.loader import load_prompts

    return load_prompts(Path(__file__).resolve().parent.parent / "schemas" / "bas-bmi")
