from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import wire
from app.title import fallback_title, make_title, normalize_title


class FakeProvider:
    def __init__(self, parts: list[str]) -> None:
        self.parts = parts
        self.calls: list[tuple[list[dict], object, dict]] = []

    async def complete(self, messages, tools=None, **kwargs):
        self.calls.append((messages, tools, kwargs))

        async def stream():
            for part in self.parts:
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=part))]
                )

        return stream()


@pytest.mark.asyncio
async def test_make_title_uses_isolated_model_request():
    provider = FakeProvider(["标题：", "补充项目测试"])

    title = await make_title(provider, "检查测试覆盖并补充测试")

    assert title == "补充项目测试"
    messages, tools, kwargs = provider.calls[0]
    assert messages[-1] == {
        "role": "user",
        "content": "检查测试覆盖并补充测试",
    }
    assert tools is None
    assert kwargs["max_tokens"] == 48


def test_normalize_title_uses_first_non_empty_line():
    assert normalize_title("\n“项目结构分析”\n额外解释") == "项目结构分析"


def test_fallback_title_collapses_whitespace_and_truncates():
    title = fallback_title("  a   " + "b" * 50)

    assert "  " not in title
    assert len(title) == 41
    assert title.endswith("…")


@pytest.mark.asyncio
async def test_update_thread_title_persists_and_refreshes(monkeypatch):
    saved: dict = {"title": "fallback"}
    runner = MagicMock()
    runner.thread.id = "thread-1"
    runner.thread.load_metainfo.return_value = saved.copy()
    monkeypatch.setattr(wire, "make_title", AsyncMock(return_value="生成项目报告"))
    emit_thread_title = MagicMock()
    monkeypatch.setattr(wire, "emit_thread_title", emit_thread_title)

    await wire.update_thread_title(runner, "生成报告")

    persisted = runner.thread.save_metainfo.call_args.args[0]
    assert persisted["title"] == "生成项目报告"
    assert persisted["title_generated"] is True
    emit_thread_title.assert_called_once_with("thread-1", "生成项目报告")
