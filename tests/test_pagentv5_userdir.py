from pathlib import Path

import pytest

from pagentv5.sandbox import Sandbox, SandboxConfig
from pagentv5.userdir import (
    UserDir,
    UserDirConfig,
    compose_tools,
    open_userdir,
    validate_resource_combination,
)


def userdir_config(tmp_path: Path, access: str) -> UserDirConfig:
    root = tmp_path / "user"
    root.mkdir(exist_ok=True)
    return UserDirConfig(access=access, path=str(root))


def test_none_userdir_has_no_path_or_cwd_fallback():
    config = UserDirConfig(access="none", path="/ignored")

    assert config.root is None
    assert open_userdir(config) is None


def test_userdir_requires_existing_path(tmp_path: Path):
    with pytest.raises(ValueError, match="path is required"):
        UserDirConfig(access="readonly")
    with pytest.raises(ValueError, match="not a directory"):
        UserDirConfig(access="readwrite", path=str(tmp_path / "missing"))


@pytest.mark.asyncio
async def test_readonly_userdir_can_read_and_list_but_not_write(tmp_path: Path):
    config = userdir_config(tmp_path, "readonly")
    (config.root / "notes.txt").write_text("hello", encoding="utf-8")
    userdir = UserDir(config)

    assert await userdir.read_text("notes.txt") == "hello"
    listing = await userdir.list()
    assert listing["entries"] == [
        {
            "name": "notes.txt",
            "path": "notes.txt",
            "type": "file",
            "size": 5,
        }
    ]
    with pytest.raises(PermissionError, match="readonly"):
        await userdir.write("notes.txt", "changed")


@pytest.mark.asyncio
async def test_userdir_rejects_path_escape_and_symlink_escape(tmp_path: Path):
    config = userdir_config(tmp_path, "readonly")
    outside = tmp_path / "outside"
    outside.mkdir()
    (config.root / "link").symlink_to(outside)
    userdir = UserDir(config)

    with pytest.raises(ValueError, match="escapes user directory"):
        await userdir.read("../outside/secret")
    with pytest.raises(ValueError, match="escapes user directory"):
        await userdir.read("link/secret")


def test_compose_tools_covers_resource_matrix(tmp_path: Path):
    none = UserDirConfig()
    readonly = userdir_config(tmp_path, "readonly")
    readwrite = userdir_config(tmp_path, "readwrite")

    assert compose_tools(SandboxConfig(backend="none"), none) == []
    assert compose_tools(SandboxConfig(backend="none"), readonly) == ["list_host_files"]
    assert compose_tools(SandboxConfig(backend="none"), readwrite) == [
        "run_command",
        "read_file",
        "write_file",
        "str_replace",
        "list_dir",
    ]
    assert compose_tools(SandboxConfig(backend="local"), readonly) == [
        "run_command",
        "read_file",
        "write_file",
        "str_replace",
        "list_dir",
        "list_host_files",
        "copy_from_host",
    ]
    assert compose_tools(SandboxConfig(backend="local"), readwrite)[-3:] == [
        "list_host_files",
        "copy_from_host",
        "copy_to_host",
    ]


def test_ssh_readwrite_combination_is_rejected(tmp_path: Path):
    sandbox = SandboxConfig(
        backend="ssh",
        connection={"host": "example.test", "user": "agent"},
    )
    with pytest.raises(ValueError, match="does not support readwrite"):
        validate_resource_combination(
            sandbox,
            userdir_config(tmp_path, "readwrite"),
        )


@pytest.mark.asyncio
async def test_readwrite_userdir_becomes_direct_workroot(tmp_path: Path):
    userdir = UserDir(userdir_config(tmp_path, "readwrite"))
    tools = userdir.tools()

    assert [tool.name for tool in tools] == [
        "run_command",
        "read_file",
        "write_file",
        "str_replace",
        "list_dir",
    ]
    output = await tools[2].acall('{"path":"result.txt","content":"done"}')
    assert output.ok is True
    assert await userdir.read_text("result.txt") == "done"


@pytest.mark.asyncio
async def test_userdir_bridge_copies_both_directions(tmp_path: Path):
    config = userdir_config(tmp_path, "readwrite")
    (config.root / "input.txt").write_text("input", encoding="utf-8")
    userdir = UserDir(config)

    async with await Sandbox.open(
        SandboxConfig(backend="local"),
        tmp_path / "workspace",
    ) as sandbox:
        tools = userdir.tools(sandbox)
        assert [tool.name for tool in tools] == [
            "list_host_files",
            "copy_from_host",
            "copy_to_host",
        ]

        copied_in = await tools[1].acall('{"host_path":"input.txt"}')
        assert copied_in.ok is True
        assert await sandbox.files.read_text("input.txt") == "input"

        await sandbox.files.write("output.txt", "output")
        copied_out = await tools[2].acall('{"source":"output.txt","dest":"deliveries"}')
        assert copied_out.ok is True
        assert await userdir.read_text("deliveries/output.txt") == "output"
