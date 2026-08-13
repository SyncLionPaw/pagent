import pytest

from pagentv4 import (
    FunctionTool,
    ProviderHandoff,
    ProviderIdentity,
    RunEnd,
    Runner,
    ToolCallBegin,
    TurnEnd,
)


class FakeStreamChunk:
    def __init__(self, *, content=None, reasoning=None, tool_calls=None):
        delta = type(
            "Delta",
            (),
            {
                "content": content,
                "reasoning_content": reasoning,
                "tool_calls": tool_calls,
            },
        )()
        self.choices = [type("Choice", (), {"delta": delta})()]


class FakeProvider:
    def __init__(self, steps):
        self.steps = list(steps)

    async def complete(self, messages, tools=None, **run_kwargs):
        chunks = self.steps.pop(0)

        async def stream():
            for chunk in chunks:
                yield chunk

        return stream()


def local_provider_identity() -> ProviderIdentity:
    return ProviderIdentity(
        name="local",
        kind="ollama",
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434/v1",
    )


async def open_runner(tmp_path, monkeypatch, provider, *, tools=(), max_turns=24):
    monkeypatch.chdir(tmp_path)
    return await Runner.create(
        "test",
        provider,
        overrides={"backend": "local"},
        max_turns=max_turns,
        tools=tools,
    )


def tool_call_chunk(
    *,
    call_id: str = "call_1",
    name: str = "echo",
    arguments: str = '{"x": 1}',
):
    function = type(
        "Function",
        (),
        {"name": name, "arguments": arguments},
    )()
    tool_call = type(
        "ToolCall",
        (),
        {"index": 0, "id": call_id, "type": "function", "function": function},
    )()
    return FakeStreamChunk(tool_calls=[tool_call])


@pytest.mark.asyncio
async def test_runner_cancel_run_emits_cancelled_turn_end(tmp_path, monkeypatch):
    provider = FakeProvider(
        [
            [FakeStreamChunk(content="part1"), FakeStreamChunk(content="part2")],
            [FakeStreamChunk(content="unused")],
        ]
    )
    runner = await open_runner(tmp_path, monkeypatch, provider)
    try:
        events = []
        async for event in runner.run("hi"):
            events.append(event)
            if len(events) == 2:
                runner.cancel_run()
        ended = [event for event in events if isinstance(event, TurnEnd)]
        run_ended = [event for event in events if isinstance(event, RunEnd)]
        assert ended[-1].stop_reason == "cancelled"
        assert ended[-1].stopped is True
        assert run_ended[-1].stop_reason == "cancelled"
        assert runner.run_state.phase == "ended"
        assert runner.run_state.stop_reason == "cancelled"
        assert not runner.run_state.active
    finally:
        await runner.close()


@pytest.mark.asyncio
async def test_runner_steer_appends_user_message(tmp_path, monkeypatch):
    async def echo_tool(x: int) -> str:
        return f"echo:{x}"

    provider = FakeProvider(
        [
            [tool_call_chunk()],
            [FakeStreamChunk(content="done")],
        ]
    )
    runner = await open_runner(
        tmp_path,
        monkeypatch,
        provider,
        tools=[
            FunctionTool(
                "echo",
                "echo",
                {
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": ["x"],
                },
                echo_tool,
            )
        ],
        max_turns=4,
    )
    try:
        async for event in runner.run("start"):
            if isinstance(event, TurnEnd) and event.stop_reason == "continuing":
                runner.steer("follow up")
        users = [
            message.content.text
            for message in runner.messages.data
            if message.role == "user"
        ]
        assert users == ["start", "follow up"]
    finally:
        await runner.close()


@pytest.mark.asyncio
async def test_runner_steer_during_tool_round_is_deferred(tmp_path, monkeypatch):
    async def echo_tool(x: int) -> str:
        return f"echo:{x}"

    provider = FakeProvider(
        [
            [tool_call_chunk()],
            [FakeStreamChunk(content="done")],
        ]
    )
    runner = await open_runner(
        tmp_path,
        monkeypatch,
        provider,
        tools=[
            FunctionTool(
                "echo",
                "echo",
                {
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": ["x"],
                },
                echo_tool,
            )
        ],
        max_turns=4,
    )
    try:
        async for event in runner.run("start"):
            if isinstance(event, ToolCallBegin):
                runner.steer("too early")
                users = [
                    message.content.text
                    for message in runner.messages.data
                    if message.role == "user"
                ]
                assert users == ["start"]
        users = [
            message.content.text
            for message in runner.messages.data
            if message.role == "user"
        ]
        assert users == ["start", "too early"]
    finally:
        await runner.close()


@pytest.mark.asyncio
async def test_runner_exposes_inbound_mailbox(tmp_path, monkeypatch):
    provider = FakeProvider([[FakeStreamChunk(content="ok")]])
    runner = await open_runner(tmp_path, monkeypatch, provider)
    try:
        assert runner.inbound is not None
        runner.steer("queued")
        assert runner.inbound.pending() == 1
    finally:
        await runner.close()


@pytest.mark.asyncio
async def test_runner_handoff_persists_and_switches_provider(tmp_path, monkeypatch):
    original = FakeProvider([])
    replacement = FakeProvider([[FakeStreamChunk(content="from replacement")]])
    runner = await open_runner(tmp_path, monkeypatch, original)
    try:
        identity = local_provider_identity()
        message = runner.handoff(replacement, identity, reason="use local model")

        assert runner.agent.provider is replacement
        assert runner.active_provider_identity == identity
        assert message.role == "control"
        assert isinstance(message.content, ProviderHandoff)
        assert message.content.reason == "use local model"

        persisted = runner.thread.load_messages()
        assert persisted.data[-1] == message

        texts = [text async for text in runner.run("continue", return_type="text")]
        assert texts == ["from replacement"]
    finally:
        await runner.close()


@pytest.mark.asyncio
async def test_runner_handoff_restores_active_provider(tmp_path, monkeypatch):
    runner = await open_runner(tmp_path, monkeypatch, FakeProvider([]))
    root = runner.thread.root.parent
    identity = local_provider_identity()
    runner.handoff(FakeProvider([]), identity)
    await runner.close()

    resumed = await Runner.create(
        "test",
        FakeProvider([]),
        root=root,
        overrides={"backend": "local"},
    )
    try:
        assert resumed.active_provider_identity == identity
        assert isinstance(resumed.messages.data[-1].content, ProviderHandoff)
    finally:
        await resumed.close()


@pytest.mark.asyncio
async def test_runner_handoff_rejects_active_run(tmp_path, monkeypatch):
    runner = await open_runner(tmp_path, monkeypatch, FakeProvider([]))
    try:
        runner.run_state.phase = "generating"

        with pytest.raises(RuntimeError, match="generating"):
            runner.handoff(FakeProvider([]), local_provider_identity())

        assert not any(
            isinstance(message.content, ProviderHandoff)
            for message in runner.messages.data
        )
    finally:
        await runner.close()


@pytest.mark.asyncio
async def test_runner_handoff_waits_for_run_teardown(tmp_path, monkeypatch):
    runner = await open_runner(
        tmp_path,
        monkeypatch,
        FakeProvider([[FakeStreamChunk(content="done")]]),
    )
    try:
        async for event in runner.run("start"):
            if not isinstance(event, RunEnd):
                continue
            assert runner.run_state.phase == "ended"
            with pytest.raises(RuntimeError, match="run is in progress"):
                runner.handoff(FakeProvider([]), local_provider_identity())

        identity = local_provider_identity()
        runner.handoff(FakeProvider([]), identity)
        assert runner.active_provider_identity == identity
    finally:
        await runner.close()


@pytest.mark.asyncio
async def test_runner_handoff_rolls_back_when_persistence_fails(tmp_path, monkeypatch):
    original = FakeProvider([])
    replacement = FakeProvider([])
    runner = await open_runner(tmp_path, monkeypatch, original)

    def fail_flush():
        raise OSError("disk full")

    monkeypatch.setattr(runner, "flush_conversation", fail_flush)
    try:
        with pytest.raises(OSError, match="disk full"):
            runner.handoff(replacement, local_provider_identity())

        assert runner.agent.provider is original
        assert not any(
            isinstance(message.content, ProviderHandoff)
            for message in runner.messages.data
        )
    finally:
        await runner.close()
