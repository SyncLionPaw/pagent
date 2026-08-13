import pytest
from pydantic import ValidationError

from pagentv4 import (
    Message,
    Messages,
    ProviderHandoff,
    ProviderIdentity,
    resolve_active_provider_identity,
)


def provider_identity(
    name: str,
    kind: str,
    model: str,
    base_url: str,
) -> ProviderIdentity:
    return ProviderIdentity(
        name=name,
        kind=kind,
        model=model,
        base_url=base_url,
    )


def test_messages_jsonl_round_trip(tmp_path):
    messages = Messages()
    messages += Message.system("You are helpful.", message_id="m-system")
    messages += Message.user("hello", turn_id=1)
    messages += Message.assistant(
        {"type": "thinking", "text": "let me think"}, turn_id=1
    )
    messages += Message.assistant({"type": "text", "text": "done"}, turn_id=1)
    messages += Message.assistant(
        {
            "type": "function",
            "id": "call_1",
            "name": "search",
            "arguments": '{"q":"x"}',
        },
        turn_id=1,
    )
    messages += Message.tool_result("call_1", "ok", turn_id=1)

    path = tmp_path / "messages.jsonl"
    messages.save_to_jsonl(path)

    restored = Messages.load_from_jsonl(path)

    assert restored == messages
    assert restored.data[0].message_id == "m-system"
    assert restored.data[0].turn_id == 0
    assert restored.data[1].turn_id == 1
    assert all(message.message_id for message in restored.data)
    assert path.read_text(encoding="utf-8").count("\n") == len(messages)


def test_provider_handoff_jsonl_round_trip(tmp_path):
    previous = provider_identity(
        "deepseek",
        "deepseek",
        "deepseek-v4-flash",
        "https://api.deepseek.com",
    )
    current = provider_identity(
        "kimi",
        "kimi",
        "kimi-k2.5",
        "https://api.moonshot.cn/v1",
    )
    messages = Messages()
    messages += Message.provider_handoff(
        previous,
        current,
        reason="long-context task",
        message_id="handoff-1",
        turn_id=2,
    )

    path = tmp_path / "messages.jsonl"
    messages.save_to_jsonl(path)
    restored = Messages.load_from_jsonl(path)

    assert restored == messages
    handoff = restored.data[0]
    assert handoff.role == "control"
    assert isinstance(handoff.content, ProviderHandoff)
    assert handoff.content.previous == previous
    assert handoff.content.current == current
    assert handoff.content.reason == "long-context task"


def test_provider_handoff_is_excluded_from_openai_payload():
    deepseek = provider_identity(
        "deepseek",
        "deepseek",
        "deepseek-v4-flash",
        "https://api.deepseek.com",
    )
    kimi = provider_identity(
        "kimi",
        "kimi",
        "kimi-k2.5",
        "https://api.moonshot.cn/v1",
    )
    messages = Messages()
    messages += Message.user("first")
    messages += Message.assistant({"type": "text", "text": "before"})
    messages += Message.provider_handoff(deepseek, kimi)
    messages += Message.user("continue")

    assert messages.to_openai() == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "before"},
        {"role": "user", "content": "continue"},
    ]


def test_provider_handoff_requires_control_role():
    previous = provider_identity(
        "deepseek",
        "deepseek",
        "deepseek-v4-flash",
        "https://api.deepseek.com",
    )
    current = provider_identity(
        "kimi",
        "kimi",
        "kimi-k2.5",
        "https://api.moonshot.cn/v1",
    )

    with pytest.raises(ValidationError, match="assistant message"):
        Message.model_validate(
            {
                "role": "assistant",
                "content": ProviderHandoff(
                    previous=previous,
                    current=current,
                ),
            }
        )


def test_provider_handoff_rejects_same_provider():
    identity = provider_identity(
        "deepseek",
        "deepseek",
        "deepseek-v4-flash",
        "https://api.deepseek.com",
    )

    with pytest.raises(ValidationError, match="must differ"):
        ProviderHandoff(previous=identity, current=identity)


def test_resolve_active_provider_identity_folds_handoff_chain():
    deepseek = provider_identity(
        "deepseek",
        "deepseek",
        "deepseek-v4-flash",
        "https://api.deepseek.com",
    )
    kimi = provider_identity(
        "kimi",
        "kimi",
        "kimi-k2.5",
        "https://api.moonshot.cn/v1",
    )
    local = provider_identity(
        "local",
        "ollama",
        "qwen3:8b",
        "http://127.0.0.1:11434/v1",
    )
    messages = Messages()
    messages += Message.provider_handoff(deepseek, kimi)
    messages += Message.provider_handoff(kimi, local)

    assert resolve_active_provider_identity(deepseek, messages.data) == local


def test_resolve_active_provider_identity_rejects_broken_chain():
    deepseek = provider_identity(
        "deepseek",
        "deepseek",
        "deepseek-v4-flash",
        "https://api.deepseek.com",
    )
    kimi = provider_identity(
        "kimi",
        "kimi",
        "kimi-k2.5",
        "https://api.moonshot.cn/v1",
    )
    local = provider_identity(
        "local",
        "ollama",
        "qwen3:8b",
        "http://127.0.0.1:11434/v1",
    )
    messages = Messages()
    messages += Message.provider_handoff(kimi, local, message_id="broken")

    with pytest.raises(ValueError, match="broken"):
        resolve_active_provider_identity(deepseek, messages.data)


def test_provider_identity_rejects_blank_fields():
    with pytest.raises(ValidationError, match="non-empty"):
        provider_identity(" ", "deepseek", "deepseek-v4-flash", "https://example.com")


def test_to_openai_reasoning_only_assistant_uses_empty_content():
    messages = Messages()
    messages += Message.assistant({"type": "thinking", "text": "plan only"})
    api = messages.to_openai()
    assert api == [
        {"role": "assistant", "content": "", "reasoning_content": "plan only"}
    ]


def test_to_openai_keeps_complete_tool_round():
    messages = Messages()
    messages += Message.user("run")
    messages += Message.assistant(
        {
            "type": "function",
            "id": "call_1",
            "name": "echo",
            "arguments": "{}",
        }
    )
    messages += Message.tool_result("call_1", "ok")
    api = messages.to_openai()
    assert api[1]["content"] is None
    assert api[1]["tool_calls"][0]["id"] == "call_1"
    assert api[2] == {"role": "tool", "tool_call_id": "call_1", "content": "ok"}


def test_to_openai_drops_incomplete_tool_round_before_user():
    messages = Messages()
    messages += Message.user("run")
    messages += Message.assistant(
        {
            "type": "function",
            "id": "call_1",
            "name": "echo",
            "arguments": "{}",
        }
    )
    messages += Message.user("next")

    assert messages.to_openai() == [
        {"role": "user", "content": "run"},
        {"role": "user", "content": "next"},
    ]


def test_to_openai_drops_stray_tool_result():
    messages = Messages()
    messages += Message.user("run")
    messages += Message.tool_result("missing_call", "late")
    messages += Message.user("next")

    assert messages.to_openai() == [
        {"role": "user", "content": "run"},
        {"role": "user", "content": "next"},
    ]


def test_complete_orphan_tool_results_appends_placeholder():
    messages = Messages()
    messages += Message.user("go", turn_id=1)
    messages += Message.assistant(
        {
            "type": "function",
            "id": "call_orphan",
            "name": "run_command",
            "arguments": "{}",
        },
        turn_id=1,
    )
    messages += Message.user("stop", turn_id=2)

    added = messages.complete_orphan_tool_results()

    assert added == 1
    assert messages.data[-1].role == "tool"
    assert messages.data[-1].content.tool_call_id == "call_orphan"
    assert messages.data[-1].turn_id == 1
