"""Application configuration. Env-backed via pydantic-settings (MAG_ prefix).

Carried forward from the archived config.py, trimmed to what the restart engine
needs. Vertex AI fields are kept because R0.5 proved we extract via Vertex.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    data_dir: Path = Field(default=Path("./data"))
    runs_dir: Path = Field(default=Path("./data/runs"))
    exports_dir: Path = Field(default=Path("./exports"))
    schemas_dir: Path = Field(default=Path("./schemas"))
    rules_dir: Path = Field(default=Path("./rules"))

    # Active schema profile (folder under schemas/)
    schema_name: str = Field(default="bas-bmi", min_length=1)

    # LLM providers
    default_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_attempts: int = Field(default=5, ge=1)
    gemini_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Vertex AI backend for Gemini (R0.5-proven path).
    gemini_use_vertex: bool = Field(default=False)
    gcp_project: str | None = None
    gcp_location: str = "global"
    gcp_credentials_path: Path | None = None

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.runs_dir, self.exports_dir):
            p.mkdir(parents=True, exist_ok=True)
