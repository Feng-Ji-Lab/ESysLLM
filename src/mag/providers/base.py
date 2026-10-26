"""Provider abstraction. The only translator between wire JSON and internal models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PField


class ProviderError(Exception):
    """Raised when a provider call fails or returns unusable output."""


class Asset(BaseModel):
    """An image asset (figure/table PNG) passed to a multimodal call."""

    model_config = ConfigDict(extra="forbid")

    path: str
    mime_type: str = "image/png"
    data: bytes


class WireResponse(BaseModel):
    """Raw provider output plus token accounting. Inflation happens elsewhere."""

    model_config = ConfigDict(extra="forbid")

    data: dict[str, Any]
    prompt_tokens: int = PField(default=0, ge=0)
    completion_tokens: int = PField(default=0, ge=0)
    raw_text: str = ""


class Provider(ABC):
    """Each impl wraps one LLM backend. Subclasses must set `name`."""

    name: str = "base"

    @abstractmethod
    def extract_section(
        self,
        *,
        wire_schema: dict,
        system_prompt: str,
        user_prompt: str,
        assets: list[Asset],
    ) -> WireResponse: ...

    @abstractmethod
    def aggregate_field(
        self,
        *,
        wire_schema: dict,
        system_prompt: str,
        user_prompt: str,
    ) -> WireResponse: ...
