from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from pagentv4.sandbox.base import (
    BackendIdentity,
    CommandResult,
    DirEntry,
    SandboxError,
    SandboxLimits,
    SandboxNotStartedError,
)


@dataclass(frozen=True, slots=True)
class SandboxSpec:
    workdir: str | None = None
    home: str = "/home/agent"
    image: str | None = None
    command: tuple[str, ...] | None = None
    env: dict[str, str] = field(default_factory=dict)
    connection: dict[str, str] = field(default_factory=dict)
    default_limits: SandboxLimits = field(default_factory=SandboxLimits)
    container_ttl_seconds: int | None = None


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


__all__ = [
    "BackendIdentity",
    "CommandResult",
    "DirEntry",
    "SandboxBackend",
    "SandboxError",
    "SandboxLimits",
    "SandboxNotStartedError",
    "SandboxSpec",
]
