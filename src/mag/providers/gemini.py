"""Gemini provider over Vertex AI. Multimodal, JSON-mode via response_schema.

Mirrors the proven pattern from R0.5 (scripts/r0_5_feasibility.py) and the
archived provider: vertexai client via ADC, 429 retry with backoff, thoughts
tokens folded into completion. extract_section and aggregate_field both delegate
to _generate; the only difference is whether image assets are attached.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import TYPE_CHECKING, Any

from mag.providers.base import Asset, Provider, ProviderError, WireResponse

if TYPE_CHECKING:
    from mag.settings import Settings

_log = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError
except Exception:  # pragma: no cover
    genai = None
    types = None
    ClientError = None


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        use_vertex: bool = False,
        project: str | None = None,
        location: str = "global",
        max_attempts: int = 5,
        retry_base_delay: float = 1.0,
        temperature: float = 0.0,
    ) -> None:
        if genai is None:
            raise RuntimeError("google-genai not installed")
        self.model = model
        self.max_attempts = max_attempts
        self.retry_base_delay = retry_base_delay
        self.temperature = temperature
        if use_vertex:
            self._client = genai.Client(vertexai=True, project=project, location=location)
        else:
            self._client = genai.Client(api_key=api_key)

    @classmethod
    def from_settings(cls, s: Settings) -> GeminiProvider:
        if s.gemini_use_vertex:
            if not s.gcp_project:
                raise ValueError("gemini_use_vertex=True requires MAG_GCP_PROJECT")
            if s.gcp_credentials_path is not None:
                os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(s.gcp_credentials_path))
            return cls(
                model=s.gemini_model,
                use_vertex=True,
                project=s.gcp_project,
                location=s.gcp_location,
                max_attempts=s.gemini_max_attempts,
                temperature=s.gemini_temperature,
            )
        return cls(
            model=s.gemini_model,
            api_key=s.gemini_api_key or "",
            max_attempts=s.gemini_max_attempts,
            temperature=s.gemini_temperature,
        )

    def _generate_with_retry(self, **kwargs: Any) -> Any:
        for attempt in range(self.max_attempts):
            try:
                return self._client.models.generate_content(**kwargs)
            except ClientError as exc:  # pragma: no cover - network path
                if getattr(exc, "code", None) != 429 or attempt == self.max_attempts - 1:
                    raise
                delay = self.retry_base_delay * (2**attempt) * random.uniform(0.5, 1.5)
                _log.warning(
                    "Gemini 429 (attempt %d/%d); retry in %.2fs",
                    attempt + 1,
                    self.max_attempts,
                    delay,
                )
                time.sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover

    def _generate(
        self, *, wire_schema: dict, system_prompt: str, user_prompt: str, assets: list[Asset]
    ) -> WireResponse:
        parts: list[Any] = [types.Part(text=user_prompt)]
        for a in assets:
            parts.append(types.Part(inline_data=types.Blob(mime_type=a.mime_type, data=a.data)))

        response = self._generate_with_retry(
            model=self.model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=wire_schema,
                temperature=self.temperature,
                max_output_tokens=65536,
            ),
        )
        text = getattr(response, "text", None)
        if not text:
            raise ProviderError("empty response from gemini")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"non-JSON response: {exc}") from exc

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = (getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        cand = (getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        thoughts = (getattr(usage, "thoughts_token_count", 0) or 0) if usage else 0
        return WireResponse(
            data=data,
            prompt_tokens=prompt_tokens,
            completion_tokens=cand + thoughts,
            raw_text=text,
        )

    def extract_section(
        self, *, wire_schema: dict, system_prompt: str, user_prompt: str, assets: list[Asset]
    ) -> WireResponse:
        return self._generate(
            wire_schema=wire_schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assets=assets,
        )

    def aggregate_field(
        self, *, wire_schema: dict, system_prompt: str, user_prompt: str
    ) -> WireResponse:
        return self._generate(
            wire_schema=wire_schema,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            assets=[],
        )
