"""GeminiProvider unit tests — client is monkeypatched, no live calls."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from mag.providers.base import WireResponse
from mag.providers.gemini import GeminiProvider


class _FakeModels:
    def __init__(self, payload: dict):
        self._payload = payload
        self.last_kwargs = None

    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        usage = SimpleNamespace(
            prompt_token_count=11, candidates_token_count=7, thoughts_token_count=3
        )
        return SimpleNamespace(text=json.dumps(self._payload), usage_metadata=usage, candidates=[])


def _provider_with(payload: dict) -> tuple[GeminiProvider, _FakeModels]:
    p = GeminiProvider.__new__(GeminiProvider)  # bypass __init__/client construction
    p.model = "gemini-2.5-flash"
    p.max_attempts = 1
    p.retry_base_delay = 0.0
    p.temperature = 0.0  # set by __init__ in production; _generate reads it
    fake = _FakeModels(payload)
    p._client = SimpleNamespace(models=fake)
    return p, fake


def test_extract_section_returns_wireresponse_and_tokens():
    p, _fake = _provider_with({"Sample": {"extract_value": "None"}})
    resp = p.extract_section(
        wire_schema={"type": "object"}, system_prompt="s", user_prompt="u", assets=[]
    )
    assert isinstance(resp, WireResponse)
    assert resp.data == {"Sample": {"extract_value": "None"}}
    assert resp.prompt_tokens == 11
    assert resp.completion_tokens == 10  # 7 candidates + 3 thoughts


def test_extract_section_passes_schema_and_system_instruction():
    p, fake = _provider_with({"ok": True})
    p.extract_section(
        wire_schema={"type": "object", "x": 1}, system_prompt="SYS", user_prompt="u", assets=[]
    )
    cfg = fake.last_kwargs["config"]
    assert cfg.response_schema == {"type": "object", "x": 1}
    assert cfg.system_instruction == "SYS"
    assert cfg.response_mime_type == "application/json"


def test_aggregate_field_works_without_assets():
    p, _fake = _provider_with({"resolved_samples": []})
    resp = p.aggregate_field(wire_schema={"type": "object"}, system_prompt="s", user_prompt="u")
    assert resp.data == {"resolved_samples": []}


def test_empty_text_raises_provider_error():
    from mag.providers.base import ProviderError

    p, fake = _provider_with({})
    fake.generate_content = lambda **k: SimpleNamespace(text="", usage_metadata=None, candidates=[])
    with pytest.raises(ProviderError):
        p.extract_section(wire_schema={}, system_prompt="s", user_prompt="u", assets=[])


def test_generate_uses_temperature_zero():
    p, fake = _provider_with({"ok": True})
    p.aggregate_field(wire_schema={"type": "object"}, system_prompt="s", user_prompt="u")
    assert fake.last_kwargs["config"].temperature == 0.0
