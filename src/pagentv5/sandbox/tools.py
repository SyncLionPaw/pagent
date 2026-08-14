import json

from ..tools import FunctionTool
from .sandbox import Sandbox
from .text import prepare_read_file_output

WORKROOT_TOOLS = (
    "run_command",
    "read_file",
    "write_file",
    "str_replace",
    "list_dir",
)
DEFAULT_READ_MAX_OUTPUT = 200_000


def build_workroot_tools(sandbox: Sandbox) -> list[FunctionTool]:
    return [
        make_run_command(sandbox),
        make_read_file(sandbox),
        make_write_file(sandbox),
        make_str_replace(sandbox),
        make_list_dir(sandbox),
    ]


def make_run_command(sandbox: Sandbox) -> FunctionTool:
    async def run_command(command: str, timeout: float | None = None) -> str:
        result = await sandbox.commands.run(command, timeout=timeout)
        return json.dumps(
            {
                "ok": result.ok,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timed_out": result.timed_out,
                "stdout_truncated": result.stdout_truncated,
                "stderr_truncated": result.stderr_truncated,
            }
        )

    return FunctionTool(
        name="run_command",
        description="Run a shell command in the work root.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "number"},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
        func=run_command,
    )


def make_read_file(sandbox: Sandbox) -> FunctionTool:
    async def read_file(
        path: str,
        line_numbers: bool = False,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        content = await sandbox.files.read_text(path)
        output, error = prepare_read_file_output(
            content,
            line_numbers=line_numbers,
            start_line=start_line,
            end_line=end_line,
            max_output=DEFAULT_READ_MAX_OUTPUT,
        )
        if error:
            return json.dumps({"ok": False, "path": path, "error": error})
        return output

    return FunctionTool(
        name="read_file",
        description="Read text from a file under the work root.",
        parameters={
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
        func=read_file,
    )


def make_write_file(sandbox: Sandbox) -> FunctionTool:
    async def write_file(path: str, content: str) -> str:
        await sandbox.files.write(path, content)
        return f"wrote {path}"

    return FunctionTool(
        name="write_file",
        description="Write a complete text file under the work root.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        func=write_file,
    )


def make_str_replace(sandbox: Sandbox) -> FunctionTool:
    async def str_replace(
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        result = await sandbox.files.str_replace(
            path,
            old_string,
            new_string,
            replace_all=replace_all,
        )
        return json.dumps(result)

    return FunctionTool(
        name="str_replace",
        description="Replace exact text in a file under the work root.",
        parameters={
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
        func=str_replace,
    )


def make_list_dir(sandbox: Sandbox) -> FunctionTool:
    async def list_dir(path: str = ".") -> str:
        entries = await sandbox.files.list(path)
        return json.dumps(
            [
                {"name": entry.name, "is_dir": entry.is_dir, "size": entry.size}
                for entry in entries
            ]
        )

    return FunctionTool(
        name="list_dir",
        description="List files under the work root.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        func=list_dir,
    )
