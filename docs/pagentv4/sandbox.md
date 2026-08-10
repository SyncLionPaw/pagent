# pagentv4 Sandbox

语言：[中文](/zh/pagentv4/sandbox) | [English](/pagentv4/sandbox)

A **sandbox** is the agent's companion computer where it can run commands and
read/write files. A backend can use a managed workspace or bind the project
directory directly. Paths are normalized to a virtual home (default
`/home/agent`) across all backends.

## Quick path: `Runner.create()`

The simplest way to give an agent a computer:

```python
from pagentv4 import DeepSeek, Runner

runner = await Runner.create(
    "demo",
    DeepSeek("deepseek-v4-flash"),
    overrides={"backend": "local"},
)
try:
    async for event in runner.run(
        "List files under /home/agent, then create notes.md."
    ):
        ...
finally:
    await runner.close()
```

Flow:

1. Open thread → create sandbox from thread spec
2. Bind sandbox tools + any extra tools passed to `create()`
3. Build `AgentCore` and run via `runner.run()`
4. Close sandbox with `runner.close()`

## Backends

| `backend=` | Notes |
|------------|-------|
| `"local"` | Default. Thread workspace under `~/.pagent/threads/<thread_id>/workspaces/main/` |
| `"inplace"` | Edit the bound project directory directly, like a local coding CLI |
| `"docker"` | Container with bind mount |
| `"podman"` | Same as docker, Podman CLI |
| `"ssh"` | Remote host via asyncssh |

Run the terminal agent against the current directory:

```bash
pagent -C .
```

Bind another directory:

```bash
pagent -C /path/to/project
```

`-C PROJECT` expands to `--backend inplace --project PROJECT`. The long form
remains available for configuration and scripts.

The project path is stored in the new thread's `thread.toml`. Resuming that
thread edits the same directory even when pagent starts from another directory.
Commands and file tools operate on the project itself, so review tool approvals
and keep the project under version control.

`inplace` exposes `run_command`, `read_file`, `write_file`, `str_replace`, and
`list_dir`. Host bridge tools (`list_host_files`, `copy_from_host`,
`copy_to_host`) are omitted because the project is already the working
directory.

### Try inplace safely

Use a temporary directory for the first run:

```bash
mkdir -p /tmp/pagent-inplace-test
echo "alpha" > /tmp/pagent-inplace-test/hello.txt
pagent -C /tmp/pagent-inplace-test
```

Ask pagent:

```text
Read hello.txt, replace alpha with beta, then run cat hello.txt to verify it.
```

Approve the tool calls, exit pagent, and inspect the original file:

```bash
cat /tmp/pagent-inplace-test/hello.txt
# beta
```

The change appears directly in the bound directory. The thread stores its
conversation and configuration under `~/.pagent/threads/`; it does not create a
separate workspace for this mode.

```python
runner = await Runner.create(
    "demo",
    provider,
    overrides={"backend": "docker", "image": "python:3.12-slim"},
)
try:
    async for event in runner.run(user_input):
        ...
finally:
    await runner.close()
```

SSH example — set `ssh_host` in thread spec or overrides:

```python
runner = await Runner.create(
    "remote",
    provider,
    overrides={
        "backend": "ssh",
        "ssh_host": "user@example.com",
        "ssh_workdir": "/tmp/agent",
    },
)
```

## Workspace layout

With `thread_id="demo"`:

```text
~/.pagent/threads/demo/workspace/
```

Persistent runners using `local` get their workspace from the thread. With
`inplace`, the sandbox maps agent paths under `/home/agent` to the bound project
directory.

## Direct `Sandbox` API

For lower-level control, you can create a sandbox directly and choose a
`workspace_id` or `workdir` yourself:

```python
from pagentv4 import Sandbox

sandbox = await Sandbox.create(backend="local", workspace_id="my-project")
try:
    result = await sandbox.commands.run("ls -la")
    await sandbox.files.write("hello.txt", "hi")
    content = await sandbox.files.read_text("hello.txt")
finally:
    await sandbox.close()
```

Context manager form:

```python
async with await Sandbox.create(backend="local", workspace_id="demo") as box:
    await box.files.write("hello.txt", "hi")
```

## Built-in agent tools

`sandbox.tools()` returns eight `FunctionTool` instances (see [Tools](./tools)).
Wording shown to the model avoids internal terms like "sandbox".

## Thread integration

A [Thread](./core-types#thread) stores the sandbox spec and messages under
`~/.pagent/threads/<id>/`. The `local` backend also stores its workspace there;
`inplace` stores the bound project path in `thread.toml`. Use a thread when the
same computer and conversation must survive process restarts. See
`examples/pagentv4/runner/sandbox.py`.

## Limits

`sandbox.commands.run(..., timeout=...)` and `SandboxLimits` cap stdout,
stderr, memory, and CPU time. Defaults are conservative; tune per workload.

## Error handling

All backends follow the same boundary between "the command failed" and "the
sandbox is unusable":

| Situation | How it surfaces |
|-----------|-----------------|
| Command ran but exited nonzero, or timed out | `CommandResult(ok=False, exit_code=..., timed_out=...)` — no exception |
| Backend used before `start()` | `SandboxNotStartedError` |
| `start()` failed (CLI missing, `docker run` failed, remote `$HOME` unresolved) | `SandboxError` |
| Backend died and the guard could not restart it | `SandboxDeadError` |
| Invalid config (missing `image` / `ssh_host`) | `ValueError` |
| File semantics (missing path, dir without `recursive`) | `FileNotFoundError` / `IsADirectoryError` |

`SandboxNotStartedError` and `SandboxDeadError` both subclass `SandboxError`,
so a caller can catch the whole "sandbox unusable" class with a single
`except SandboxError`:

```python
from pagentv4 import SandboxError

try:
    result = await sandbox.commands.run("build.sh")
    if not result.ok:
        ...  # command-level failure: inspect result.exit_code / result.stderr
except SandboxError:
    ...  # lifecycle-level failure: the sandbox itself is gone
```
