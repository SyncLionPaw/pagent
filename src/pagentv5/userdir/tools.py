import json

from pagentv4.sandbox.text import prepare_read_file_output

from ..sandbox import WORKROOT_TOOLS, Sandbox, SandboxConfig
from ..tools import FunctionTool
from .config import UserDirConfig
from .userdir import UserDir

BRIDGE_TOOLS = ("list_host_files", "copy_from_host", "copy_to_host")
DEFAULT_READ_MAX_OUTPUT = 200_000


def validate_resource_combination(
    sandbox: SandboxConfig,
    userdir: UserDirConfig,
) -> None:
    if sandbox.backend == "ssh" and userdir.access == "readwrite":
        raise ValueError("ssh sandbox does not support readwrite user directory")


def compose_tools(
    sandbox: SandboxConfig,
    userdir: UserDirConfig,
) -> list[str]:
    validate_resource_combination(sandbox, userdir)
    if sandbox.backend == "none":
        if userdir.access == "readwrite":
            return list(WORKROOT_TOOLS)
        if userdir.access == "readonly":
            return ["list_host_files"]
        return []

    names = list(WORKROOT_TOOLS)
    if userdir.access == "readonly":
        names.extend(["list_host_files", "copy_from_host"])
    elif userdir.access == "readwrite":
        names.extend(BRIDGE_TOOLS)
    return names


def build_userdir_tools(
    userdir: UserDir,
    sandbox: Sandbox | None,
) -> list[FunctionTool]:
    if sandbox is None:
        if userdir.access == "readonly":
            return [make_list_host_files(userdir)]
        return build_userdir_workroot_tools(userdir)

    tools = [
        make_list_host_files(userdir),
        make_copy_from_host(userdir, sandbox),
    ]
    if userdir.access == "readwrite":
        tools.append(make_copy_to_host(userdir, sandbox))
    return tools


def build_userdir_workroot_tools(userdir: UserDir) -> list[FunctionTool]:
    return [
        make_run_command(userdir),
        make_read_file(userdir),
        make_write_file(userdir),
        make_str_replace(userdir),
        make_list_dir(userdir),
    ]


def make_run_command(userdir: UserDir) -> FunctionTool:
    async def run_command(command: str, timeout: float | None = None) -> str:
        result = await userdir.commands.run(command, timeout=timeout)
        return json.dumps(
            {
                "ok": result.ok,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
            }
        )

    return FunctionTool(
        "run_command",
        "Run a shell command in the user directory.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "number"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        run_command,
    )


def make_read_file(userdir: UserDir) -> FunctionTool:
    async def read_file(
        path: str,
        line_numbers: bool = False,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        output, error = prepare_read_file_output(
            await userdir.read_text(path),
            line_numbers=line_numbers,
            start_line=start_line,
            end_line=end_line,
            max_output=DEFAULT_READ_MAX_OUTPUT,
        )
        if error:
            return json.dumps({"ok": False, "path": path, "error": error})
        return output

    return FunctionTool(
        "read_file",
        "Read text from a file in the user directory.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "line_numbers": {"type": "boolean"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        read_file,
    )


def make_write_file(userdir: UserDir) -> FunctionTool:
    async def write_file(path: str, content: str) -> str:
        await userdir.write(path, content)
        return f"wrote {path}"

    return FunctionTool(
        "write_file",
        "Write a complete text file in the user directory.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        write_file,
    )


def make_str_replace(userdir: UserDir) -> FunctionTool:
    async def str_replace(
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        content = await userdir.read_text(path)
        count = content.count(old_string)
        if count == 0:
            return json.dumps({"ok": False, "error": "old_string not found"})
        if count > 1 and not replace_all:
            return json.dumps(
                {"ok": False, "error": f"old_string occurs {count} times"}
            )
        replacements = count if replace_all else 1
        await userdir.write(
            path,
            content.replace(old_string, new_string, replacements),
        )
        return json.dumps({"ok": True, "replacements": replacements})

    return FunctionTool(
        "str_replace",
        "Replace exact text in a user directory file.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            "required": ["path", "old_string", "new_string"],
            "additionalProperties": False,
        },
        str_replace,
    )


def make_list_dir(userdir: UserDir) -> FunctionTool:
    async def list_dir(path: str = ".") -> str:
        return json.dumps(await userdir.list(path, depth=1))

    return FunctionTool(
        "list_dir",
        "List files in the user directory.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        list_dir,
    )


def make_list_host_files(userdir: UserDir) -> FunctionTool:
    async def list_host_files(path: str = "", depth: int = 1) -> str:
        return json.dumps(await userdir.list(path, depth=depth))

    return FunctionTool(
        "list_host_files",
        "List files exposed by the user directory binding.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "depth": {"type": "integer", "minimum": 1, "maximum": 3},
            },
            "required": [],
            "additionalProperties": False,
        },
        list_host_files,
    )


def make_copy_from_host(userdir: UserDir, sandbox: Sandbox) -> FunctionTool:
    async def copy_from_host(host_path: str, dest: str = ".") -> str:
        target = await userdir.copy_to_sandbox(host_path, sandbox, dest)
        return f"copied into work root at {target}"

    return FunctionTool(
        "copy_from_host",
        "Copy a file or directory from the user directory into the work root.",
        {
            "type": "object",
            "properties": {
                "host_path": {"type": "string"},
                "dest": {"type": "string"},
            },
            "required": ["host_path"],
            "additionalProperties": False,
        },
        copy_from_host,
    )


def make_copy_to_host(userdir: UserDir, sandbox: Sandbox) -> FunctionTool:
    async def copy_to_host(source: str, dest: str = ".") -> str:
        target = await userdir.copy_from_sandbox(sandbox, source, dest)
        return f"copied into user directory at {target}"

    return FunctionTool(
        "copy_to_host",
        "Copy a file or directory from the work root into the user directory.",
        {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "dest": {"type": "string"},
            },
            "required": ["source"],
            "additionalProperties": False,
        },
        copy_to_host,
    )
