"""Tests for the Provider ABC and WireResponse."""

from __future__ import annotations

import pytest

from mag.providers.base import Provider, ProviderError, WireResponse


def test_wireresponse_fields():
    r = WireResponse(
        data={"ok": True}, prompt_tokens=10, completion_tokens=5, raw_text='{"ok": true}'
    )
    assert r.data == {"ok": True}
    assert r.prompt_tokens == 10


def test_provider_is_abstract():
    with pytest.raises(TypeError):
        Provider()  # cannot instantiate an ABC with abstract methods


def test_provider_error_is_exception():
    assert issubclass(ProviderError, Exception)


def test_subclass_must_implement_both_methods():
    class Partial(Provider):
        name = "partial"

        def extract_section(self, *, wire_schema, system_prompt, user_prompt, assets):
            return WireResponse(data={}, prompt_tokens=0, completion_tokens=0, raw_text="")

    # aggregate_field still abstract → instantiation fails
    with pytest.raises(TypeError):
        Partial()
