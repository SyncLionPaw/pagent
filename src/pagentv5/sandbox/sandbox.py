from __future__ import annotations

import os
import posixpath
from pathlib import Path
from types import TracebackType

from pagentv4.sandbox.policy import check_backend_path

from .backend import create_backend
from .config import SandboxConfig
from .protocol import (
    CommandResult,
    DirEntry,
    SandboxBackend,
    SandboxLimits,
    SandboxSpec,
)


class Commands:
    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox

    async def run(
        self,
        command: str | list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        stdin: str | None = None,
        timeout: float | None = None,
        limits: SandboxLimits | None = None,
    ) -> CommandResult:
        if isinstance(command, list):
            argv = [self.sandbox.map_command(part) for part in command]
        else:
            argv = ["sh", "-c", self.sandbox.map_command(command)]

        applied = limits
        if timeout is not None:
            base = limits or self.sandbox.spec.default_limits
            applied = SandboxLimits(
                timeout=timeout,
                stdout_bytes=base.stdout_bytes,
                stderr_bytes=base.stderr_bytes,
                memory_bytes=base.memory_bytes,
                cpu_seconds=base.cpu_seconds,
            )
        return await self.sandbox.backend.exec(
            argv,
            cwd=self.sandbox.resolve(cwd) if cwd else self.sandbox.workdir,
            env=env,
            stdin=stdin,
            limits=applied,
        )


class Files:
    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox

    async def read(self, path: str) -> bytes:
        resolved = self.sandbox.resolve(path)
        check_backend_path(resolved, workdir=self.sandbox.workdir)
        return await self.sandbox.backend.read_file(resolved)

    async def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return (await self.read(path)).decode(encoding)

    async def write(self, path: str, data: bytes | str) -> None:
        payload = data.encode("utf-8") if isinstance(data, str) else data
        resolved = self.sandbox.resolve(path)
        check_backend_path(resolved, workdir=self.sandbox.workdir)
        await self.sandbox.backend.write_file(resolved, payload)

    async def list(self, path: str = ".") -> list[DirEntry]:
        resolved = self.sandbox.resolve(path)
        check_backend_path(resolved, workdir=self.sandbox.workdir)
        return await self.sandbox.backend.list_dir(resolved)

    async def exists(self, path: str) -> bool:
        resolved = self.sandbox.resolve(path)
        check_backend_path(resolved, workdir=self.sandbox.workdir)
        return await self.sandbox.backend.exists(resolved)

    async def remove(self, path: str, *, recursive: bool = False) -> None:
        resolved = self.sandbox.resolve(path)
        check_backend_path(resolved, workdir=self.sandbox.workdir)
        await self.sandbox.backend.remove(resolved, recursive=recursive)

    async def str_replace(
        self,
        path: str,
        old_string: str,
        new_string: str,
        *,
        replace_all: bool = False,
    ) -> dict[str, object]:
        content = await self.read_text(path)
        count = content.count(old_string)
        if count == 0:
            return {"ok": False, "path": path, "error": "old_string not found"}
        if count > 1 and not replace_all:
            return {
                "ok": False,
                "path": path,
                "error": f"old_string occurs {count} times",
            }
        replacements = count if replace_all else 1
        await self.write(path, content.replace(old_string, new_string, replacements))
        return {"ok": True, "path": path, "replacements": replacements}


class Sandbox:
    def __init__(
        self,
        backend: SandboxBackend,
        config: SandboxConfig,
        workdir: str,
    ) -> None:
        resolved_workdir = str(Path(workdir).expanduser().resolve())
        self.backend = backend
        self.config = config
        self.workdir = resolved_workdir
        self.home = posixpath.normpath(config.home)
        self.spec = SandboxSpec(
            workdir=resolved_workdir,
            home=self.home,
            image=config.image,
            env=dict(config.env),
            connection=dict(config.connection),
            default_limits=config.default_limits,
            container_ttl_seconds=config.container_ttl_seconds,
        )
        self.commands = Commands(self)
        self.files = Files(self)
        self.started = False

    @classmethod
    async def open(
        cls,
        config: SandboxConfig,
        workdir: str | Path,
        *,
        backend: SandboxBackend | None = None,
        bind_mounts: tuple[str, ...] = (),
    ) -> Sandbox:
        if config.backend == "none":
            raise ValueError("cannot open sandbox with backend 'none'")
        Path(workdir).expanduser().resolve().mkdir(parents=True, exist_ok=True)
        sandbox = cls(
            backend or create_backend(config, bind_mounts=bind_mounts),
            config,
            str(workdir),
        )
        await sandbox.start()
        return sandbox

    async def start(self) -> None:
        if self.started:
            return
        await self.backend.start(self.spec, self.workdir)
        get_effective_workdir = getattr(self.backend, "effective_workdir", None)
        effective_workdir = (
            get_effective_workdir() if callable(get_effective_workdir) else None
        )
        if effective_workdir:
            self.workdir = effective_workdir
        self.started = True

    async def close(self) -> None:
        if not self.started:
            return
        await self.backend.close()
        self.started = False

    async def alive(self) -> bool:
        if not self.started:
            return False
        return await self.backend.alive()

    def virtual_path(self, path: str) -> str:
        if not path:
            return self.home
        if posixpath.isabs(path):
            normalized = posixpath.normpath(path)
        else:
            normalized = posixpath.normpath(posixpath.join(self.home, path))
        if normalized == self.home or normalized.startswith(f"{self.home}/"):
            return normalized
        raise ValueError(f"path escapes sandbox home: {path!r}")

    def resolve(self, path: str) -> str:
        virtual = self.virtual_path(path)
        if virtual == self.home:
            return self.workdir
        relative = virtual.removeprefix(self.home).lstrip("/")
        return os.path.normpath(os.path.join(self.workdir, relative))

    def map_command(self, command: str) -> str:
        if not command or self.home == self.workdir:
            return command
        return command.replace(self.home, self.workdir)

    def to_virtual_path(self, actual: str) -> str:
        normalized = os.path.normpath(actual)
        workdir = os.path.normpath(self.workdir)
        if normalized == workdir:
            return self.home
        if not normalized.startswith(workdir + os.sep):
            return actual
        relative = normalized[len(workdir) :].lstrip("/")
        return posixpath.join(self.home, relative.replace(os.sep, "/"))

    def tools(self):
        from .tools import build_workroot_tools

        return build_workroot_tools(self)

    async def __aenter__(self) -> Sandbox:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
