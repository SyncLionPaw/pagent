"""阶段一新增的共享命令：get_config / set_provider / thread_meta / environment_check。

沿用 test_app_wire_lazy.py 的手法：直接调 handle_command，patch wire.emit_line 收事件行。
这些命令不需要打开 runner（runner=None 也应工作），是 wire / http 共用的配置/存储面。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app import wire
from app.config import ProviderConfig, ReplConfig
from app.setup import ProviderSetup, write_user_provider
from pagentv4 import Message, ProviderIdentity


@pytest.fixture
def lines(monkeypatch):
    captured: list[str] = []
    monkeypatch.setattr(wire, "emit_line", lambda line: captured.append(line))
    return captured


def parsed(lines: list[str]) -> list[dict]:
    return [json.loads(line) for line in lines]


@pytest.mark.asyncio
async def test_get_config_emits_redacted_snapshot(lines):
    write_user_provider(
        ProviderSetup(api_key="sk-secret-1234", model="deepseek-v4-flash")
    )
    await wire.handle_command({"cmd": "get_config"}, None, ReplConfig(), {"turn": None})
    events = parsed(lines)
    assert events[0]["method"] == "ConfigSnapshot"
    provider = events[0]["params"]["provider"]
    assert provider["api_key_configured"] is True
    assert provider["api_key_masked"].endswith("1234")
    assert "sk-secret" not in provider["api_key_masked"]
    assert len(events[0]["params"]["providers"]) == 1
    assert events[0]["params"]["providers"][0]["api_key_required"] is True


@pytest.mark.asyncio
async def test_get_config_lists_named_providers(lines, monkeypatch):
    config = ReplConfig(
        providers={
            "deepseek": ProviderConfig(
                kind="deepseek",
                model="deepseek-v4-flash",
                api_key="sk-secret",
            ),
            "local": ProviderConfig(kind="ollama", model="qwen3:8b"),
        },
        agent_provider="deepseek",
    )
    monkeypatch.setattr(wire, "load_config", lambda: config)

    await wire.handle_command({"cmd": "get_config"}, None, config, {"turn": None})

    providers = parsed(lines)[0]["params"]["providers"]
    assert [provider["name"] for provider in providers] == ["deepseek", "local"]
    assert providers[1]["api_key_required"] is False
    assert providers[1]["api_key_configured"] is False


@pytest.mark.asyncio
async def test_set_provider_writes_and_reads_back(lines):
    await wire.handle_command(
        {
            "cmd": "set_provider",
            "api_key": "sk-new-key-9999",
            "model": "deepseek-v4-flash",
        },
        None,
        ReplConfig(),
        {"turn": None},
    )
    events = parsed(lines)
    assert events[-1]["method"] == "ConfigSnapshot"
    assert events[-1]["params"]["provider"]["api_key_configured"] is True
    # 真正写到了盘：再 get_config 能读到脱敏尾号。
    lines.clear()
    await wire.handle_command({"cmd": "get_config"}, None, ReplConfig(), {"turn": None})
    assert parsed(lines)[0]["params"]["provider"]["api_key_masked"].endswith("9999")


@pytest.mark.asyncio
async def test_set_provider_missing_api_key_emits_error(lines):
    await wire.handle_command(
        {"cmd": "set_provider", "api_key": ""}, None, ReplConfig(), {"turn": None}
    )
    events = parsed(lines)
    assert events[0]["method"] == "Error"


@pytest.mark.asyncio
async def test_thread_meta_missing_id_emits_error(lines):
    await wire.handle_command(
        {"cmd": "thread_meta"}, None, ReplConfig(), {"turn": None}
    )
    assert parsed(lines)[0]["method"] == "Error"


@pytest.mark.asyncio
async def test_thread_meta_returns_metainfo(lines, monkeypatch):
    class FakeThread:
        def load_metainfo(self):
            return {"title": "hello", "usage": {"total": 1}}

    monkeypatch.setattr(wire.Thread, "open", staticmethod(lambda tid: FakeThread()))
    await wire.handle_command(
        {"cmd": "thread_meta", "thread_id": "t1"}, None, ReplConfig(), {"turn": None}
    )
    event = parsed(lines)[0]
    assert event["method"] == "ThreadMeta"
    assert event["params"]["thread_id"] == "t1"
    assert event["params"]["meta"]["title"] == "hello"


@pytest.mark.asyncio
async def test_environment_check_emits_snapshot(lines):
    await wire.handle_command(
        {"cmd": "environment_check"}, None, ReplConfig(), {"turn": None}
    )
    event = parsed(lines)[0]
    assert event["method"] == "EnvironmentCheck"
    assert "api_key_configured" in event["params"]
    assert "container_runtime" in event["params"]


@pytest.mark.asyncio
async def test_handoff_provider_switches_runner_and_emits_state(lines, monkeypatch):
    config = ReplConfig(
        providers={
            "deepseek": ProviderConfig(
                kind="deepseek",
                model="deepseek-v4-flash",
                api_key="sk-deepseek",
            ),
            "local": ProviderConfig(
                kind="ollama",
                model="qwen3:8b",
                base_url="http://127.0.0.1:11434/v1",
            ),
        },
        agent_provider="deepseek",
    )
    initial = ProviderIdentity(
        name="deepseek",
        kind="deepseek",
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    )
    captured: dict = {}

    class FakeRunner:
        active_provider_identity = initial

        def handoff(self, provider, identity, *, reason=""):
            captured.update(provider=provider, identity=identity, reason=reason)
            self.active_provider_identity = identity
            return Message.provider_handoff(initial, identity, reason=reason)

    monkeypatch.setattr(wire, "refresh_provider_from_disk", lambda current: config)
    monkeypatch.setattr(
        wire,
        "build_provider",
        lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs),
    )

    runner = FakeRunner()
    returned = await wire.handle_command(
        {
            "cmd": "handoff_provider",
            "provider": "local",
            "reason": "use local",
        },
        runner,
        config,
        {"turn": None},
    )

    assert returned is runner
    assert captured["identity"].name == "local"
    assert captured["reason"] == "use local"
    assert [event["method"] for event in parsed(lines)] == [
        "ProviderHandoff",
        "ProviderState",
    ]
    assert parsed(lines)[-1]["params"]["provider"]["model"] == "qwen3:8b"


@pytest.mark.asyncio
async def test_handoff_provider_rejects_missing_api_key(lines, monkeypatch):
    config = ReplConfig(
        providers={
            "kimi": ProviderConfig(kind="kimi", model="kimi-k2.5"),
        },
        agent_provider="kimi",
    )
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setattr(wire, "refresh_provider_from_disk", lambda current: config)

    runner = SimpleNamespace()
    await wire.handle_command(
        {"cmd": "handoff_provider", "provider": "kimi"},
        runner,
        config,
        {"turn": None},
    )

    event = parsed(lines)[0]
    assert event["method"] == "Error"
    assert event["params"]["where"] == "handoff_provider"


@pytest.mark.asyncio
async def test_handoff_provider_rejects_active_turn(lines):
    active_task = SimpleNamespace(done=lambda: False)

    await wire.handle_command(
        {"cmd": "handoff_provider", "provider": "local"},
        SimpleNamespace(),
        ReplConfig(),
        {"turn": active_task},
    )

    event = parsed(lines)[0]
    assert event["method"] == "Error"
    assert event["params"]["where"] == "handoff_provider"
