from __future__ import annotations

from typing import Protocol, runtime_checkable

from pagentv4.sandbox.base import (
    BackendIdentity,
    CommandResult,
    DirEntry,
    SandboxError,
    SandboxLimits,
    SandboxNotStartedError,
    SandboxSpec,
)


@runtime_checkable
class SandboxBackend(Protocol):
    async def start(self, spec: SandboxSpec, workdir: str) -> None: ...
    async def close(self) -> None: ...
    async def alive(self) -> bool: ...

    async def exec(
        self,
        command: list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        stdin: str | None = None,
        limits: SandboxLimits | None = None,
    ) -> CommandResult: ...

    async def read_file(self, path: str) -> bytes: ...
    async def write_file(self, path: str, data: bytes) -> None: ...
    async def list_dir(self, path: str) -> list[DirEntry]: ...
    async def exists(self, path: str) -> bool: ...
    async def remove(self, path: str, *, recursive: bool = False) -> None: ...
    def describe(self, spec: SandboxSpec, workdir: str) -> BackendIdentity: ...
    def effective_workdir(self) -> str | None: ...


class CommandGuard(Protocol):
    def check(self, command: str, *, workdir: str) -> None: ...


__all__ = [
    "BackendIdentity",
    "CommandGuard",
    "CommandResult",
    "DirEntry",
    "SandboxBackend",
    "SandboxError",
    "SandboxLimits",
    "SandboxNotStartedError",
    "SandboxSpec",
]
