from pathlib import Path

import pytest

from pagentv5.sandbox import (
    DockerBackend,
    Sandbox,
    SandboxConfig,
    SandboxError,
    SandboxLimits,
    SandboxSpec,
    create_backend,
)


def test_sandbox_config_validates_backend_requirements():
    assert SandboxConfig(backend="none").backend == "none"

    with pytest.raises(ValueError, match="requires image"):
        SandboxConfig(backend="container")
    with pytest.raises(ValueError, match="host and user"):
        SandboxConfig(backend="ssh")
    with pytest.raises(ValueError, match="absolute virtual path"):
        SandboxConfig(home="relative")


def test_none_backend_has_no_implementation():
    with pytest.raises(ValueError, match="has no implementation"):
        create_backend(SandboxConfig(backend="none"))


@pytest.mark.asyncio
async def test_local_sandbox_files_commands_and_lifecycle(tmp_path: Path):
    sandbox = await Sandbox.open(
        SandboxConfig(
            backend="local",
            command_policy="open",
            default_limits=SandboxLimits(timeout=5),
        ),
        tmp_path / "workspace",
    )

    assert await sandbox.alive() is True
    await sandbox.files.write("hello.txt", "hello")
    assert await sandbox.files.read_text("/home/agent/hello.txt") == "hello"
    assert [entry.name for entry in await sandbox.files.list()] == ["hello.txt"]

    result = await sandbox.commands.run("pwd")
    assert result.ok is True
    assert result.stdout.strip() == str((tmp_path / "workspace").resolve())

    await sandbox.close()
    assert await sandbox.alive() is False


@pytest.mark.asyncio
async def test_sandbox_rejects_paths_outside_work_root(tmp_path: Path):
    async with await Sandbox.open(
        SandboxConfig(backend="local"),
        tmp_path / "workspace",
    ) as sandbox:
        with pytest.raises(ValueError, match="escapes sandbox home"):
            await sandbox.files.read("../secret")
        with pytest.raises(ValueError, match="escapes sandbox home"):
            await sandbox.files.read("/tmp/secret")


@pytest.mark.asyncio
async def test_workdir_guard_blocks_command_escape(tmp_path: Path):
    async with await Sandbox.open(
        SandboxConfig(backend="local", command_policy="workdir"),
        tmp_path / "workspace",
    ) as sandbox:
        result = await sandbox.commands.run("cat ../secret")

    assert result.ok is False
    assert result.exit_code == 126
    assert "parent directory" in result.stderr


@pytest.mark.asyncio
async def test_sandbox_projects_five_workroot_tools(tmp_path: Path):
    async with await Sandbox.open(
        SandboxConfig(backend="local"),
        tmp_path / "workspace",
    ) as sandbox:
        assert [tool.name for tool in sandbox.tools()] == [
            "run_command",
            "read_file",
            "write_file",
            "str_replace",
            "list_dir",
        ]


def test_missing_container_runtime_is_a_sandbox_error(monkeypatch):
    from pagentv5.sandbox import backend

    monkeypatch.setattr(backend.shutil, "which", lambda _name: None)
    with pytest.raises(SandboxError, match="docker / podman"):
        backend.detect_container_cli()


@pytest.mark.asyncio
async def test_container_backend_mounts_workdir_and_userdir(
    monkeypatch, tmp_path: Path
):
    workdir = tmp_path / "workspace"
    userdir = tmp_path / "user"
    workdir.mkdir()
    userdir.mkdir()
    captured: list[str] = []

    class Process:
        returncode = 0

        async def communicate(self):
            return b"container-id\n", b""

    async def create_subprocess_exec(*argv, **kwargs):
        del kwargs
        captured.extend(argv)
        return Process()

    monkeypatch.setattr(
        "pagentv5.sandbox.container.shutil.which",
        lambda name: name,
    )
    monkeypatch.setattr(
        "pagentv5.sandbox.container.asyncio.create_subprocess_exec",
        create_subprocess_exec,
    )
    backend = DockerBackend(bind_mounts=(str(userdir),))

    await backend.start(
        SandboxSpec(image="pagent:test"),
        str(workdir),
    )

    mounts = [
        captured[index + 1] for index, item in enumerate(captured) if item == "-v"
    ]
    assert mounts == [
        f"{workdir}:{workdir}",
        f"{userdir}:{userdir}",
    ]
