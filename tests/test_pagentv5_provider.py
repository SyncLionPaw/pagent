from types import SimpleNamespace

import pytest

from pagentv5.provider import PROVIDER_CATALOG, Provider, ProviderMessageBase


async def empty_stream():
    if False:
        yield None


def test_catalog_selects_api_protocol_by_provider():
    assert PROVIDER_CATALOG["openai"]["api_protocol"] == "openai-responses"
    assert PROVIDER_CATALOG["deepseek"]["api_protocol"] == "openai-completions"


def test_provider_uses_catalog_defaults():
    provider = Provider(" gpt-5 ", provider_id=" OpenAI ", api_key="key")

    assert provider.provider_id == "openai"
    assert provider.model_id == "gpt-5"
    assert provider.api_protocol == "openai-responses"
    assert provider.base_url == "https://api.openai.com/v1"


def test_provider_requires_hosted_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Provider("gpt-5", provider_id="openai")


def test_empty_api_key_falls_back_to_provider_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")

    provider = Provider("gpt-5", provider_id="openai", api_key="")

    assert provider.api_key == "environment-key"


def test_provider_allows_local_endpoint_without_api_key(monkeypatch):
    monkeypatch.delenv("VLLM_API_KEY", raising=False)

    provider = Provider("local-model", provider_id="vllm")

    assert provider.api_key == "not-needed"


def test_provider_allows_api_protocol_override():
    provider = Provider(
        "gpt-5",
        provider_id="openai",
        api_protocol="openai-completions",
        api_key="key",
    )

    assert provider.api_protocol == "openai-completions"


def test_provider_supports_custom_endpoint_without_provider_id():
    provider = Provider(
        "relay-model",
        api_protocol="openai-completions",
        base_url="https://relay.example.com/v1",
        api_key="relay-key",
    )

    assert provider.provider_id is None
    assert provider.model_id == "relay-model"
    assert provider.api_protocol == "openai-completions"
    assert provider.base_url == "https://relay.example.com/v1"
    assert provider.api_key == "relay-key"


def test_custom_endpoint_allows_missing_api_key():
    provider = Provider(
        "relay-model",
        api_protocol="openai-completions",
        base_url="http://127.0.0.1:8080/v1",
    )

    assert provider.api_key == "not-needed"


def test_custom_endpoint_requires_api_and_base_url():
    with pytest.raises(ValueError, match="api_protocol is required"):
        Provider("relay-model", base_url="https://relay.example.com/v1")

    with pytest.raises(ValueError, match="base_url is required"):
        Provider("relay-model", api_protocol="openai-completions")


@pytest.mark.asyncio
async def test_responses_api_uses_responses_endpoint():
    captured: dict = {}

    class Responses:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return empty_stream()

    provider = Provider("gpt-5", provider_id="openai", api_key="key")
    provider.client = SimpleNamespace(responses=Responses())

    messages = [
        message
        async for message in provider.complete(
            "hello",
            [{"type": "function", "name": "search", "parameters": {}}],
            temperature=0.2,
        )
    ]

    assert all(isinstance(message, ProviderMessageBase) for message in messages)
    assert captured == {
        "temperature": 0.2,
        "model": "gpt-5",
        "input": "hello",
        "stream": True,
        "tools": [{"type": "function", "name": "search", "parameters": {}}],
    }


@pytest.mark.asyncio
async def test_completions_api_uses_chat_endpoint():
    captured: dict = {}

    class Completions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return empty_stream()

    provider = Provider("deepseek-chat", provider_id="deepseek", api_key="key")
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=Completions()),
    )
    messages = [{"role": "user", "content": "hello"}]

    output = [message async for message in provider.complete(messages)]

    assert all(isinstance(message, ProviderMessageBase) for message in output)
    assert captured == {
        "model": "deepseek-chat",
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }


@pytest.mark.asyncio
async def test_chat_completions_rejects_string_input():
    provider = Provider("deepseek-chat", provider_id="deepseek", api_key="key")

    with pytest.raises(TypeError, match="list of messages"):
        await anext(provider.complete("hello"))


def test_provider_rejects_reserved_request_kwargs():
    with pytest.raises(TypeError, match="reserved keys"):
        Provider(
            "gpt-5",
            provider_id="openai",
            api_key="key",
            request_kwargs={"model": "other"},
        )
