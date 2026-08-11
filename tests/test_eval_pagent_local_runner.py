from pagentv4 import DeepSeek, Provider
from pagentv4.adapters.harbor_runner import (
    add_usage,
    build_provider,
    model_id,
)


def test_model_id_removes_harbor_provider_prefix():
    assert model_id("deepseek/deepseek-chat") == "deepseek-chat"
    assert model_id("custom-model") == "custom-model"


def test_build_provider_selects_deepseek(monkeypatch):
    monkeypatch.delenv("PAGENT_BENCH_BASE_URL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    provider = build_provider("deepseek/deepseek-chat")

    assert isinstance(provider, DeepSeek)
    assert provider.model_id == "deepseek-chat"


def test_build_provider_supports_custom_endpoint(monkeypatch):
    monkeypatch.setenv("PAGENT_BENCH_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("PAGENT_BENCH_API_KEY", "test-key")

    provider = build_provider("local/custom-model")

    assert type(provider) is Provider
    assert provider.model_id == "custom-model"
    assert provider.base_url == "https://example.com/v1"


def test_add_usage_accepts_openai_fields():
    total = {"input_tokens": 0, "output_tokens": 0, "cache_tokens": 0}

    add_usage(
        total,
        {
            "prompt_tokens": 12,
            "completion_tokens": 3,
            "prompt_tokens_details": {"cached_tokens": 4},
        },
    )

    assert total == {"input_tokens": 12, "output_tokens": 3, "cache_tokens": 4}
