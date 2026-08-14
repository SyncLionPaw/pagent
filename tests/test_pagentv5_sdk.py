from pathlib import Path

import pytest

from pagentv5 import (
    BaseAgent,
    LocalCodeAgent,
    Runner,
    SandboxWorker,
    tool,
)
from pagentv5.events import RunEnd
from pagentv5.provider import (
    ProviderMessage,
    ResponseEnd,
    TextDelta,
    ToolCallEnd,
    Usage,
)
from pagentv5.sandbox import PodmanBackend
from pagentv5.sdk.agent import parse_sandbox


def usage() -> Usage:
    return Usage(input_tokens=1, output_tokens=1)


class SequencedProvider:
    api_protocol = "openai-completions"

    def __init__(self, responses: list[list[ProviderMessage]]) -> None:
        self.responses = responses
        self.inputs: list[object] = []

    async def complete(self, input, tools=None, **request_kwargs):
        del tools, request_kwargs
        self.inputs.append(input)
        response = self.responses[len(self.inputs) - 1]
        for message in response:
            yield message


@pytest.mark.asyncio
async def test_base_agent_projects_text_and_keeps_conversation():
    provider = SequencedProvider(
        [
            [
                TextDelta(content_index=0, delta="hello"),
                ResponseEnd(stop_reason="stop", usage=usage()),
            ],
            [
                TextDelta(content_index=0, delta="again"),
                ResponseEnd(stop_reason="stop", usage=usage()),
            ],
        ]
    )
    agent = BaseAgent(
        "test-model",
        provider=provider,
        system="Be concise.",
        emit_type="text",
    )

    assert await agent.ask("hi") == "hello"
    assert [chunk async for chunk in agent.run("next")] == ["again"]

    assert provider.inputs[1] == [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "next"},
    ]
    await agent.close()


@pytest.mark.asyncio
async def test_base_agent_emits_complete_events():
    provider = SequencedProvider(
        [
            [
                TextDelta(content_index=0, delta="hello"),
                ResponseEnd(stop_reason="stop", usage=usage()),
            ]
        ]
    )
    agent = BaseAgent("test-model", provider=provider)

    assert isinstance(agent, Runner)
    events = [event async for event in agent.run("hi")]

    assert isinstance(events[-1], RunEnd)
    assert events[-1].stop_reason == "completed"


def test_sdk_accepts_max_turn_alias_and_validates_output_mode():
    provider = SequencedProvider([])
    agent = BaseAgent("test-model", provider=provider, max_turn=7)

    assert agent.max_turns == 7
    with pytest.raises(TypeError, match="not both"):
        BaseAgent(
            "test-model",
            provider=provider,
            max_turn=7,
            max_turns=8,
        )
    with pytest.raises(ValueError, match="emit_type"):
        BaseAgent("test-model", provider=provider, emit_type="message")


def test_sandbox_worker_parses_convenient_sandbox_spec():
    assert parse_sandbox("local") == ("local", None, None)
    assert parse_sandbox("ssh") == ("ssh", None, None)
    assert parse_sandbox("container:debian:bookworm") == (
        "container",
        "debian:bookworm",
        None,
    )
    assert parse_sandbox("container:podman:debian:bookworm") == (
        "container",
        "debian:bookworm",
        "podman",
    )
    with pytest.raises(ValueError, match="requires an image"):
        parse_sandbox("container:podman")

    agent = SandboxWorker(
        "test-model",
        provider=SequencedProvider([]),
        sandbox="container:podman:debian:bookworm",
    )
    assert agent.sandbox_config.backend == "container"
    assert agent.sandbox_config.image == "debian:bookworm"
    assert agent.sandbox_runtime == "podman"

    ssh_agent = SandboxWorker(
        "test-model",
        provider=SequencedProvider([]),
        sandbox="ssh",
        sandbox_connection={"host": "example.test", "user": "agent"},
    )
    assert ssh_agent.sandbox_config.backend == "ssh"


@pytest.mark.asyncio
async def test_sandbox_worker_selects_requested_container_runtime(monkeypatch):
    captured: dict[str, object] = {}

    class OpenedSandbox:
        def tools(self):
            return []

        async def close(self):
            return

    async def open_sandbox(config, workspace_path, *, backend):
        captured["config"] = config
        captured["workspace_path"] = workspace_path
        captured["backend"] = backend
        return OpenedSandbox()

    monkeypatch.setattr("pagentv5.sdk.agent.Sandbox.open", open_sandbox)
    agent = SandboxWorker(
        "test-model",
        provider=SequencedProvider([]),
        sandbox="container:podman:docker.io/library/debian:bookworm-slim",
    )

    await agent.initialize()

    assert isinstance(captured["backend"], PodmanBackend)
    assert captured["config"].image == "docker.io/library/debian:bookworm-slim"
    await agent.close()


def test_clear_preserves_system_message_from_initial_messages():
    agent = BaseAgent(
        "test-model",
        provider=SequencedProvider([]),
        messages=[
            {"role": "system", "content": "Keep this."},
            {"role": "user", "content": "Remove this."},
        ],
    )

    agent.clear()

    assert agent.messages == [{"role": "system", "content": "Keep this."}]


@pytest.mark.asyncio
async def test_non_yolo_tool_requires_approval():
    @tool()
    def add(a: int, b: int) -> int:
        return a + b

    provider = SequencedProvider(
        [
            [
                ToolCallEnd(
                    content_index=0,
                    tool_call_id="call_1",
                    name="add",
                    arguments='{"a":2,"b":3}',
                ),
                ResponseEnd(stop_reason="tool_use", usage=usage()),
            ],
            [
                TextDelta(content_index=0, delta="denied"),
                ResponseEnd(stop_reason="stop", usage=usage()),
            ],
        ]
    )
    agent = BaseAgent(
        "test-model",
        provider=provider,
        tools=[add],
        emit_type="text",
        yolo=False,
    )

    assert await agent.ask("add") == "denied"
    assert "requires approval" in provider.inputs[1][-1]["content"]


@pytest.mark.asyncio
async def test_approval_callback_allows_tool():
    @tool()
    def add(a: int, b: int) -> int:
        return a + b

    calls: list[str] = []

    async def approve(call: ToolCallEnd) -> bool:
        calls.append(call.name)
        return True

    provider = SequencedProvider(
        [
            [
                ToolCallEnd(
                    content_index=0,
                    tool_call_id="call_1",
                    name="add",
                    arguments='{"a":2,"b":3}',
                ),
                ResponseEnd(stop_reason="tool_use", usage=usage()),
            ],
            [
                TextDelta(content_index=0, delta="5"),
                ResponseEnd(stop_reason="stop", usage=usage()),
            ],
        ]
    )
    agent = BaseAgent(
        "test-model",
        provider=provider,
        tools=[add],
        approve_tool=approve,
        emit_type="text",
    )

    assert await agent.ask("add") == "5"
    assert calls == ["add"]
    assert provider.inputs[1][-1]["content"] == "5"


@pytest.mark.asyncio
async def test_local_code_agent_exposes_project_tools(tmp_path: Path):
    provider = SequencedProvider([])
    agent = LocalCodeAgent(
        "test-model",
        provider=provider,
        project_path=tmp_path,
        yolo=True,
    )

    await agent.initialize()

    assert isinstance(agent, Runner)
    assert [tool.name for tool in agent.tools] == [
        "run_command",
        "read_file",
        "write_file",
        "str_replace",
        "list_dir",
    ]
    write = agent.tool_map["write_file"]
    output = await write.acall('{"path":"hello.txt","content":"hello"}')
    assert output.ok is True
    assert (tmp_path / "hello.txt").read_text(encoding="utf-8") == "hello"
    await agent.close()


@pytest.mark.asyncio
async def test_sandbox_worker_owns_temporary_workspace():
    provider = SequencedProvider([])
    agent = SandboxWorker(
        "test-model",
        provider=provider,
        yolo=True,
    )

    await agent.initialize()
    workspace = agent.workspace_path
    assert workspace is not None
    assert workspace.is_dir()
    assert isinstance(agent, Runner)
    assert [tool.name for tool in agent.tools] == [
        "run_command",
        "read_file",
        "write_file",
        "str_replace",
        "list_dir",
    ]

    await agent.close()
    assert workspace.exists() is False


@pytest.mark.asyncio
async def test_sandbox_worker_cleans_temporary_workspace_after_open_failure(
    monkeypatch,
):
    async def fail_open(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("sandbox failed")

    monkeypatch.setattr("pagentv5.sdk.agent.Sandbox.open", fail_open)
    agent = SandboxWorker(
        "test-model",
        provider=SequencedProvider([]),
    )

    with pytest.raises(RuntimeError, match="sandbox failed"):
        await agent.initialize()

    assert agent.temporary_workspace is None
    assert agent.workspace_path is None
