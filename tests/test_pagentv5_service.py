from pathlib import Path

import pytest

from pagentv5.provider import Provider, ResponseEnd, TextDelta, ToolCallEnd, Usage
from pagentv5.sandbox import SandboxConfig
from pagentv5.service import ResourceService, endpoint_inventory
from pagentv5.session import SessionConfig
from pagentv5.task import LocalTaskBackend, ProviderBinding, TaskSpec
from pagentv5.userdir import UserDirConfig


def service_spec(tmp_path: Path) -> TaskSpec:
    userdir = tmp_path / "user"
    userdir.mkdir()
    (userdir / "input.txt").write_text("input", encoding="utf-8")
    return TaskSpec(
        provider=ProviderBinding(
            model_id="test-model",
            provider_id=None,
            api_protocol="openai-completions",
            base_url="https://example.test/v1",
        ),
        sandbox=SandboxConfig(backend="local"),
        userdir=UserDirConfig(access="readonly", path=str(userdir)),
        session=SessionConfig(storage="jsonl", root="messages"),
    )


@pytest.mark.asyncio
async def test_resource_service_exposes_task_session_and_filesystems(tmp_path: Path):
    service = ResourceService(LocalTaskBackend(tmp_path / "tasks"))
    created = await service.create_task(
        service_spec(tmp_path),
        task_id="task-1",
        title="Research",
    )

    assert created["id"] == "task-1"
    assert service.list_tasks()[0]["title"] == "Research"
    sandbox_status = await service.sandbox_status("task-1")
    assert sandbox_status["backend"] == "local"
    assert sandbox_status["alive"] is True
    assert (await service.userdir_status("task-1"))["access"] == "readonly"
    assert (await service.userdir_tree("task-1"))["entries"][0]["name"] == "input.txt"

    task = await service.get_task("task-1")
    await task.sandbox.files.write("result.txt", "result")
    assert (await service.sandbox_tree("task-1"))[0]["name"] == "result.txt"
    assert await service.read_sandbox_file("task-1", "result.txt") == b"result"
    assert await service.read_userdir_file("task-1", "input.txt") == b"input"

    await service.replace_session(
        "task-1",
        [{"role": "user", "content": "hello"}],
    )
    assert await service.session_messages("task-1") == [
        {"role": "user", "content": "hello"}
    ]
    await service.clear_session("task-1")
    assert await service.session_messages("task-1") == []
    await service.close()


@pytest.mark.asyncio
async def test_resource_service_run_persists_provider_transcript(
    tmp_path: Path,
    monkeypatch,
):
    async def complete(self, input, tools=None, **request_kwargs):
        del self, input, tools, request_kwargs
        yield TextDelta(content_index=0, delta="hello")
        yield ResponseEnd(
            stop_reason="stop",
            usage=Usage(input_tokens=1, output_tokens=1),
        )

    monkeypatch.setattr(Provider, "complete", complete)
    service = ResourceService(LocalTaskBackend(tmp_path / "tasks"))
    await service.create_task(
        TaskSpec(
            provider=ProviderBinding(
                model_id="test-model",
                provider_id=None,
                api_protocol="openai-completions",
                base_url="https://example.test/v1",
            ),
            sandbox=SandboxConfig(backend="none"),
            userdir=UserDirConfig(access="none"),
            session=SessionConfig(storage="memory"),
        ),
        task_id="task-1",
    )

    events = [event async for event in service.run("task-1", "hi")]

    assert events[-1].type == "run_end"
    assert await service.session_messages("task-1") == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    await service.close()


@pytest.mark.asyncio
async def test_resource_service_persists_tool_round_in_session(
    tmp_path: Path,
    monkeypatch,
):
    request_count = 0

    async def complete(self, input, tools=None, **request_kwargs):
        nonlocal request_count
        del self, input, tools, request_kwargs
        if request_count == 0:
            request_count += 1
            yield ToolCallEnd(
                content_index=0,
                tool_call_id="call_1",
                name="write_file",
                arguments='{"path":"note.txt","content":"saved"}',
            )
            yield ResponseEnd(
                stop_reason="tool_use", usage=Usage(input_tokens=1, output_tokens=1)
            )
            return
        yield TextDelta(content_index=0, delta="done")
        yield ResponseEnd(
            stop_reason="stop",
            usage=Usage(input_tokens=2, output_tokens=1),
        )

    monkeypatch.setattr(Provider, "complete", complete)
    service = ResourceService(LocalTaskBackend(tmp_path / "tasks"))
    await service.create_task(
        TaskSpec(
            provider=ProviderBinding(
                model_id="test-model",
                provider_id=None,
                api_protocol="openai-completions",
                base_url="https://example.test/v1",
            ),
            sandbox=SandboxConfig(backend="local"),
            session=SessionConfig(storage="jsonl", root="messages"),
        ),
        task_id="task-1",
    )

    events = [event async for event in service.run("task-1", "save a note")]
    messages = await service.session_messages("task-1")

    assert events[-1].type == "run_end"
    assert messages[0] == {"role": "user", "content": "save a note"}
    assert messages[1]["tool_calls"][0]["function"]["name"] == "write_file"
    assert messages[2] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "wrote note.txt",
    }
    assert messages[3] == {"role": "assistant", "content": "done"}
    task = await service.get_task("task-1")
    assert await task.sandbox.files.read_text("note.txt") == "saved"
    await service.close()


@pytest.mark.asyncio
async def test_resource_service_soft_deletes_task(tmp_path: Path):
    service = ResourceService(LocalTaskBackend(tmp_path / "tasks"))
    await service.create_task(
        TaskSpec(
            sandbox=SandboxConfig(backend="none"),
            session=SessionConfig(storage="memory"),
        ),
        task_id="task-1",
    )

    await service.delete_task("task-1")

    assert service.list_tasks() == []
    with pytest.raises(FileNotFoundError, match="deleted"):
        await service.open_task("task-1")


def test_endpoint_inventory_maps_legacy_frontends_to_shared_functions():
    endpoints = {endpoint["name"]: endpoint for endpoint in endpoint_inventory()}

    assert endpoints["task.list"]["implementation"] == "ResourceService.list_tasks"
    assert "wire:list_threads" in endpoints["task.list"]["legacy_names"]
    assert "desktop:list-threads" in endpoints["task.list"]["legacy_names"]
    assert endpoints["run.start"]["streaming"] is True
