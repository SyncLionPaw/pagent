"""wire 带图消息：自动切到声明 vision 的 provider，缺失时报错不发给纯文本模型。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app import wire
from app.config import ProviderConfig, ReplConfig
from pagentv4.core.message import ProviderIdentity


def make_config() -> ReplConfig:
    return ReplConfig(
        providers={
            "deepseek": ProviderConfig(
                kind="deepseek", model="deepseek-v4-flash", api_key="sk-flash"
            ),
            "vis": ProviderConfig(
                kind="deepseek",
                model="deepseek-v4-flash-vision-exp",
                api_key="sk-vis",
                vision=True,
            ),
        },
        agent_provider="deepseek",
    )


def make_runner(active_name: str) -> MagicMock:
    runner = MagicMock()
    runner.active_provider_identity = ProviderIdentity(
        name=active_name,
        kind="deepseek",
        model="deepseek-v4-flash" if active_name == "deepseek" else "vis-model",
        base_url="https://api.deepseek.com",
    )
    return runner


def test_ensure_vision_switches_when_current_is_text(monkeypatch):
    config = make_config()
    monkeypatch.setattr(wire, "refresh_provider_from_disk", lambda cfg: config)
    switched: list[str] = []

    def fake_switch(runner, cfg, name, *, reason=""):
        switched.append(name)
        return ProviderIdentity(
            name=name,
            kind="deepseek",
            model="deepseek-v4-flash-vision-exp",
            base_url="https://api.deepseek.com",
        )

    monkeypatch.setattr(wire, "switch_runner_provider", fake_switch)

    wire.ensure_vision_provider(make_runner("deepseek"), config)
    assert switched == ["vis"]


def test_ensure_vision_noop_when_current_is_vision(monkeypatch):
    config = make_config()
    monkeypatch.setattr(wire, "refresh_provider_from_disk", lambda cfg: config)

    def fail_switch(*_args, **_kwargs):
        raise AssertionError("should not switch when already vision")

    monkeypatch.setattr(wire, "switch_runner_provider", fail_switch)

    wire.ensure_vision_provider(make_runner("vis"), config)


def test_ensure_vision_raises_without_vision_provider(monkeypatch):
    config = ReplConfig(
        providers={
            "deepseek": ProviderConfig(
                kind="deepseek", model="deepseek-v4-flash", api_key="sk-flash"
            )
        },
        agent_provider="deepseek",
    )
    monkeypatch.setattr(wire, "refresh_provider_from_disk", lambda cfg: config)

    with pytest.raises(ValueError, match="没有支持视觉的 provider"):
        wire.ensure_vision_provider(make_runner("deepseek"), config)


@pytest.mark.asyncio
async def test_user_with_images_ensures_vision_then_runs(monkeypatch):
    config = make_config()
    calls: list[str] = []

    monkeypatch.setattr(
        wire, "ensure_vision_provider", lambda runner, cfg: calls.append("ensure")
    )
    monkeypatch.setattr(wire, "touch_thread_metainfo", lambda runner, text: False)

    async def fake_turn(runner, text, cfg, state, *, generate_title, images):
        calls.append(f"turn:{images}")

    monkeypatch.setattr(wire, "run_user_turn", fake_turn)

    runner = make_runner("deepseek")
    state: dict = {"turn": None}
    await wire.handle_command(
        {"cmd": "user", "text": "这啥", "images": ["data:image/png;base64,AAAA"]},
        runner,
        config,
        state,
    )
    # 等后台 turn task 跑完
    if state["turn"] is not None:
        await state["turn"]
    assert calls[0] == "ensure"
    assert any(item.startswith("turn:") for item in calls)


@pytest.mark.asyncio
async def test_user_with_images_aborts_when_vision_missing(monkeypatch):
    config = make_config()
    errors: list[tuple[str, str]] = []

    def fail_vision(runner, cfg):
        raise ValueError("当前没有支持视觉的 provider")

    monkeypatch.setattr(wire, "ensure_vision_provider", fail_vision)
    monkeypatch.setattr(
        wire, "emit_error", lambda message, where: errors.append((message, where))
    )

    def fail_turn(*_args, **_kwargs):
        raise AssertionError("turn must not start when vision provider missing")

    monkeypatch.setattr(wire, "run_user_turn", fail_turn)
    monkeypatch.setattr(wire, "touch_thread_metainfo", lambda runner, text: False)

    runner = make_runner("deepseek")
    state: dict = {"turn": None}
    await wire.handle_command(
        {"cmd": "user", "text": "看图", "images": ["data:image/png;base64,AAAA"]},
        runner,
        config,
        state,
    )
    assert state["turn"] is None
    assert errors and errors[0][1] == "user"
