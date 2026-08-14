from __future__ import annotations

import asyncio
import os
import shutil
import time

from .error import SandboxError, SandboxNotStartedError
from .local import decode_truncated, kill_and_drain
from .protocol import (
    BackendIdentity,
    CommandResult,
    DirEntry,
    SandboxLimits,
    SandboxSpec,
)


class ContainerBackend:
    def __init__(
        self,
        cli: str,
        computer_name: str,
        *,
        bind_mounts: tuple[str, ...] = (),
    ) -> None:
        self.cli = cli
        self.computer_name = computer_name
        self.bind_mounts = tuple(
            str(os.path.abspath(os.path.expanduser(path))) for path in bind_mounts
        )
        self.container_id: str | None = None
        self.workdir: str = ""
        self.spec: SandboxSpec | None = None

    async def start(self, spec: SandboxSpec, workdir: str) -> None:
        if not spec.image:
            raise ValueError(f"{self.cli} backend requires image")
        if shutil.which(self.cli) is None:
            raise SandboxError(f"{self.cli} CLI not found in PATH")

        os.makedirs(workdir, exist_ok=True)
        self.spec = spec
        self.workdir = workdir

        mounts = tuple(dict.fromkeys((workdir, *self.bind_mounts)))
        argv: list[str] = [self.cli, "run", "-d", "--rm"]
        for mount in mounts:
            if not os.path.isdir(mount):
                raise ValueError(f"container bind mount is not a directory: {mount}")
            argv.extend(["-v", f"{mount}:{mount}"])
        argv.extend(["-w", workdir])
        for key, value in spec.env.items():
            argv.extend(["--env", f"{key}={value}"])
        if spec.command:
            argv.append(spec.image)
            argv.extend(spec.command)
        else:
            ttl = spec.container_ttl_seconds
            argv.extend(
                [spec.image, "sleep", str(ttl) if ttl is not None else "infinity"]
            )

        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise SandboxError(f"{self.cli} run failed: {detail}")
        self.container_id = stdout.decode("utf-8", errors="replace").strip()

    async def close(self) -> None:
        if not self.container_id:
            return
        process = await asyncio.create_subprocess_exec(
            self.cli,
            "rm",
            "-f",
            self.container_id,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.wait()
        self.container_id = None

    async def alive(self) -> bool:
        if not self.container_id:
            return False
        process = await asyncio.create_subprocess_exec(
            self.cli,
            "inspect",
            "-f",
            "{{.State.Running}}",
            self.container_id,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await process.communicate()
        if process.returncode != 0:
            return False
        return stdout.decode("utf-8", errors="replace").strip() == "true"

    async def exec(
        self,
        command: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        stdin: str | None = None,
        limits: SandboxLimits | None = None,
    ) -> CommandResult:
        if not self.container_id:
            raise SandboxNotStartedError(f"{self.cli} backend not started")
        applied = limits or (self.spec.default_limits if self.spec else SandboxLimits())
        run_cwd = cwd or self.workdir

        argv: list[str] = [self.cli, "exec", "-i", "-w", run_cwd]
        for key, value in (env or {}).items():
            argv.extend(["--env", f"{key}={value}"])
        argv.append(self.container_id)
        argv.extend(command)

        started = time.monotonic()
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdin_bytes = stdin.encode("utf-8") if stdin is not None else None
        timed_out = False
        try:
            stdout_raw, stderr_raw = await asyncio.wait_for(
                process.communicate(stdin_bytes), timeout=applied.timeout
            )
        except asyncio.TimeoutError:
            timed_out = True
            stdout_raw, stderr_raw = await kill_and_drain(process)

        stdout, stdout_trunc = decode_truncated(stdout_raw, applied.stdout_bytes)
        stderr, stderr_trunc = decode_truncated(stderr_raw, applied.stderr_bytes)
        exit_code = process.returncode if process.returncode is not None else -1
        return CommandResult(
            ok=(exit_code == 0 and not timed_out),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=time.monotonic() - started,
            stdout_truncated=stdout_trunc,
            stderr_truncated=stderr_trunc,
            timed_out=timed_out,
        )

    async def read_file(self, path: str) -> bytes:
        with open(path, "rb") as fp:
            return fp.read()

    async def write_file(self, path: str, data: bytes) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as fp:
            fp.write(data)

    async def list_dir(self, path: str) -> list[DirEntry]:
        entries: list[DirEntry] = []
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            is_dir = os.path.isdir(full)
            try:
                size = None if is_dir else os.path.getsize(full)
            except FileNotFoundError:
                continue
            entries.append(DirEntry(name=name, is_dir=is_dir, size=size))
        return entries

    async def exists(self, path: str) -> bool:
        return os.path.exists(path)

    async def remove(self, path: str, *, recursive: bool = False) -> None:
        if not os.path.exists(path):
            return
        if os.path.isdir(path) and not os.path.islink(path):
            if not recursive:
                raise IsADirectoryError(f"{path} is a directory; pass recursive=True")
            shutil.rmtree(path)
            return
        os.remove(path)

    def describe(self, spec: SandboxSpec, workdir: str) -> BackendIdentity:
        lines: list[str] = []
        if spec and spec.image:
            lines.append(f"镜像：{spec.image}")
        if self.container_id:
            lines.append(f"容器 ID：{self.container_id[:12]}")
        home = spec.home if spec else "/home/agent"
        lines.extend(
            [
                f"run_command 的容器 shell 工作目录：{workdir}",
                f"文件工具路径 {home} 会映射到这个容器目录。",
                f"容器挂载映射：宿主 {workdir} -> 容器 {workdir}",
            ]
        )
        return BackendIdentity(
            computer_name=self.computer_name,
            extra=("\n".join(lines) + "\n") if lines else "",
        )


class DockerBackend(ContainerBackend):
    def __init__(self, *, bind_mounts: tuple[str, ...] = ()) -> None:
        super().__init__(
            "docker",
            "Docker backend",
            bind_mounts=bind_mounts,
        )


class PodmanBackend(ContainerBackend):
    def __init__(self, *, bind_mounts: tuple[str, ...] = ()) -> None:
        super().__init__(
            "podman",
            "Podman backend",
            bind_mounts=bind_mounts,
        )
