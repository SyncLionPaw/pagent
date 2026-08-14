from pathlib import Path

import pytest

from pagentv5.sandbox import SandboxConfig, SandboxLimits
from pagentv5.session import SessionConfig
from pagentv5.task import (
    LocalTaskBackend,
    ProviderBinding,
    TaskBackend,
    TaskSpec,
    dump_task_toml,
    load_task_toml,
)
from pagentv5.userdir import UserDirConfig


def make_userdir(tmp_path: Path) -> UserDirConfig:
    userdir = tmp_path / "user"
    userdir.mkdir()
    return UserDirConfig(access="readwrite", path=str(userdir))


def task_spec(tmp_path: Path) -> TaskSpec:
    return TaskSpec(
        provider=ProviderBinding(
            name="main",
            model_id="test-model",
            provider_id=None,
            api_protocol="openai-completions",
            base_url="https://example.test/v1",
        ),
        sandbox=SandboxConfig(
            backend="local",
            env={"MODE": "test"},
            default_limits=SandboxLimits(timeout=10),
        ),
        userdir=make_userdir(tmp_path),
        session=SessionConfig(storage="jsonl", root="messages"),
    )


def test_task_spec_toml_roundtrip(tmp_path: Path):
    spec = task_spec(tmp_path).with_lock("/tmp/task.toml")
    path = tmp_path / "task.toml"
    path.write_text(dump_task_toml(spec.to_dict()), encoding="utf-8")

    loaded = TaskSpec.from_dict(load_task_toml(path))

    assert loaded == spec
    assert '[sandbox]\nbackend = "local"' in path.read_text(encoding="utf-8")
    assert "compute =" not in path.read_text(encoding="utf-8")
    assert "[sandbox.limits]" in path.read_text(encoding="utf-8")
    assert "[sandbox.env]" in path.read_text(encoding="utf-8")


def test_task_spec_reads_legacy_sandbox_compute():
    spec = TaskSpec.from_dict({"sandbox": {"compute": "none"}})

    assert spec.sandbox.backend == "none"
    assert spec.to_dict()["sandbox"]["backend"] == "none"
    assert "compute" not in spec.to_dict()["sandbox"]


@pytest.mark.asyncio
async def test_open_migrates_legacy_sandbox_compute(tmp_path: Path):
    backend = LocalTaskBackend(tmp_path / "tasks")
    task = await backend.create("legacy-task", task_spec(tmp_path))
    await task.close()
    legacy_text = task.spec_path.read_text(encoding="utf-8")
    task.spec_path.write_text(
        legacy_text.replace('backend = "local"', 'compute = "local"').replace(
            "schema_version = 2",
            "schema_version = 1",
        ),
        encoding="utf-8",
    )

    migrated = await backend.open("legacy-task")
    await migrated.close()

    migrated_text = task.spec_path.read_text(encoding="utf-8")
    assert 'backend = "local"' in migrated_text
    assert "compute =" not in migrated_text
    assert "schema_version = 2" in migrated_text


@pytest.mark.asyncio
async def test_local_task_holds_resources_and_persists_session(tmp_path: Path):
    backend = LocalTaskBackend(tmp_path / "tasks")
    assert isinstance(backend, TaskBackend)

    task = await backend.create("task-1", task_spec(tmp_path))
    assert task.sandbox is not None
    assert task.userdir is not None
    assert task.session.messages == []
    assert task.tool_names() == [
        "run_command",
        "read_file",
        "write_file",
        "str_replace",
        "list_dir",
        "list_host_files",
        "copy_from_host",
        "copy_to_host",
    ]
    assert [tool.name for tool in task.tools()] == task.tool_names()
    assert task.spec.file_self_fs_pos == str(task.spec_path.resolve())

    task.session.append({"role": "user", "content": "remember this"})
    await task.close()

    reopened = await backend.open("task-1")
    assert reopened.session.messages == [{"role": "user", "content": "remember this"}]
    await reopened.close()


@pytest.mark.asyncio
async def test_task_without_sandbox_uses_userdir_as_workroot(tmp_path: Path):
    backend = LocalTaskBackend(tmp_path / "tasks")
    spec = TaskSpec(
        sandbox=SandboxConfig(backend="none"),
        userdir=make_userdir(tmp_path),
        session=SessionConfig(storage="memory"),
    )

    task = await backend.create("cursor-task", spec)

    assert task.sandbox is None
    assert task.workspace_path is None
    assert [tool.name for tool in task.tools()] == [
        "run_command",
        "read_file",
        "write_file",
        "str_replace",
        "list_dir",
    ]
    await task.close()


@pytest.mark.asyncio
async def test_task_can_have_no_filesystem_resources(tmp_path: Path):
    backend = LocalTaskBackend(tmp_path / "tasks")
    task = await backend.create(
        "chat-task",
        TaskSpec(
            sandbox=SandboxConfig(backend="none"),
            userdir=UserDirConfig(access="none"),
            session=SessionConfig(storage="memory"),
        ),
    )

    assert task.sandbox is None
    assert task.userdir is None
    assert task.tools() == []
    await task.close()


@pytest.mark.asyncio
async def test_task_list_metadata_and_soft_delete(tmp_path: Path):
    backend = LocalTaskBackend(tmp_path / "tasks")
    task = await backend.create("task-1", task_spec(tmp_path))
    await task.close()
    metadata = backend.metadata("task-1")
    metadata["title"] = "Research"
    backend.save_metadata("task-1", metadata)

    summaries = backend.list()
    assert len(summaries) == 1
    assert summaries[0].title == "Research"
    assert summaries[0].sandbox_backend == "local"
    assert summaries[0].userdir_path == str((tmp_path / "user").resolve())

    backend.delete("task-1")
    assert backend.list() == []
    assert backend.list(include_deleted=True)[0].deleted is True
    with pytest.raises(FileNotFoundError, match="deleted"):
        await backend.open("task-1")


@pytest.mark.asyncio
async def test_task_identity_is_frozen(tmp_path: Path):
    backend = LocalTaskBackend(tmp_path / "tasks")
    task = await backend.create("task-1", task_spec(tmp_path))
    await task.close()

    text = task.spec_path.read_text(encoding="utf-8")
    task.spec_path.write_text(
        text.replace(
            str(task.spec_path.resolve()),
            str(tmp_path / "other" / "task.toml"),
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="lock path mismatch"):
        await backend.open("task-1")
