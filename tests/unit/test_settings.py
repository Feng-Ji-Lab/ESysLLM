"""Tests for mag.settings."""

from __future__ import annotations

from pathlib import Path

from mag.settings import Settings


def test_defaults_present(monkeypatch):
    # Clear MAG_ vars and ignore the .env file so defaults are deterministic.
    for var in (
        "MAG_DEFAULT_PROVIDER",
        "MAG_GEMINI_MODEL",
        "MAG_GCP_LOCATION",
        "MAG_SCHEMA_NAME",
        "MAG_GEMINI_MAX_ATTEMPTS",
    ):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.default_provider == "gemini"
    assert s.gemini_model == "gemini-2.5-flash"
    assert s.gcp_location == "global"
    assert s.gemini_max_attempts >= 1
    assert s.schema_name == "bas-bmi"


def test_env_override(monkeypatch):
    monkeypatch.setenv("MAG_GEMINI_USE_VERTEX", "true")
    monkeypatch.setenv("MAG_GCP_PROJECT", "proj-123")
    monkeypatch.setenv("MAG_SCHEMA_NAME", "custom")
    s = Settings(_env_file=None)
    assert s.gemini_use_vertex is True
    assert s.gcp_project == "proj-123"
    assert s.schema_name == "custom"


def test_credentials_path_is_path(monkeypatch):
    monkeypatch.setenv("MAG_GCP_CREDENTIALS_PATH", "/projects/secrets/vertex-sa.json")
    s = Settings(_env_file=None)
    assert isinstance(s.gcp_credentials_path, Path)
