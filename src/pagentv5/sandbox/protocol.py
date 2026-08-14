from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    timeout: float | None = None
    stdout_bytes: int | None = 1024 * 1024
    stderr_bytes: int | None = 256 * 1024
    memory_bytes: int | None = None
    cpu_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class CommandResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    timed_out: bool = False


@dataclass(frozen=True, slots=True)
class DirEntry:
    name: str
    is_dir: bool
    size: int | None = None


@dataclass(frozen=True, slots=True)
class BackendIdentity:
    computer_name: str
    extra: str = ""


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
    "SandboxLimits",
    "SandboxSpec",
]
