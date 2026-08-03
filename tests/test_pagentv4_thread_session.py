import pytest

from pagentv4 import DeepSeek, Runner


@pytest.mark.asyncio
async def test_runner_open_local(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = await Runner.create(
        "demo",
        DeepSeek("deepseek-v4-flash", apikey="test-key"),
        overrides={"backend": "local", "model": "deepseek-v4-flash"},
        extra_system="你是 pagent 。",
        max_turns=24,
    )
    assert isinstance(runner, Runner)
    assert runner.thread.created is True
    assert runner.agent.max_turns == 24
    assert runner.sandbox.workdir == str(
        tmp_path / ".pagent" / "threads" / "demo" / "workspaces" / "main"
    )
    assert runner.messages.data == []
    await runner.close()


@pytest.mark.asyncio
async def test_runner_uses_explicit_thread_root(tmp_path):
    root = tmp_path / "runtime"
    runner = await Runner.create(
        "cloud-thread",
        DeepSeek("deepseek-v4-flash", apikey="test-key"),
        root=root,
        overrides={"backend": "local"},
    )
    try:
        assert runner.thread.root == root / "cloud-thread"
        assert runner.sandbox.workdir == str(
            root / "cloud-thread" / "workspaces" / "main"
        )
    finally:
        await runner.close()
