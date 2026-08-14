from __future__ import annotations

import os
import posixpath
from pathlib import Path

from ..sandbox import CommandResult, Sandbox, SandboxLimits
from .config import UserDirConfig
from .local import LocalUserDirBackend
from .protocol import UserDirBackend


class UserDirCommands:
    def __init__(self, userdir: UserDir) -> None:
        self.userdir = userdir

    async def run(
        self,
        command: str,
        *,
        timeout: float | None = None,
    ) -> CommandResult:
        self.userdir.require_write()
        limits = SandboxLimits(timeout=timeout)
        backend = self.userdir.backend
        execute = getattr(backend, "exec", None)
        if not callable(execute):
            raise RuntimeError("user directory backend does not support commands")
        return await execute(
            ["sh", "-c", command],
            cwd=str(self.userdir.root),
            limits=limits,
        )


class UserDir:
    def __init__(
        self,
        config: UserDirConfig,
        backend: UserDirBackend | None = None,
    ) -> None:
        root = config.root
        if root is None:
            raise ValueError("cannot open user directory with access 'none'")
        self.config = config
        self.root = root
        self.backend = backend or LocalUserDirBackend()
        self.commands = UserDirCommands(self)

    @property
    def access(self) -> str:
        return self.config.access

    def require_write(self) -> None:
        if self.access != "readwrite":
            raise PermissionError("user directory is readonly")

    def resolve(self, path: str, *, allow_missing: bool = True) -> Path:
        raw = (path or "").strip() or "."
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve(strict=False)
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError(f"path escapes user directory: {path!r}")
        if not allow_missing and not resolved.exists():
            raise FileNotFoundError(f"user directory path not found: {resolved}")
        return resolved

    def display_path(self, path: Path) -> str:
        if path == self.root:
            return "."
        return path.relative_to(self.root).as_posix()

    async def read(self, path: str) -> bytes:
        resolved = self.resolve(path, allow_missing=False)
        return await self.backend.read_file(str(resolved))

    async def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return (await self.read(path)).decode(encoding)

    async def write(self, path: str, data: bytes | str) -> None:
        self.require_write()
        payload = data.encode("utf-8") if isinstance(data, str) else data
        await self.backend.write_file(str(self.resolve(path)), payload)

    async def remove(self, path: str, *, recursive: bool = False) -> None:
        self.require_write()
        await self.backend.remove(str(self.resolve(path)), recursive=recursive)

    async def list(self, path: str = "", depth: int = 1) -> dict[str, object]:
        if depth < 1 or depth > 3:
            raise ValueError("depth must be 1..3")
        target = self.resolve(path)
        if not target.exists():
            return {
                "ok": False,
                "path": self.display_path(target),
                "error": "path not found",
                "entries": [],
            }
        if target.is_file():
            return {
                "ok": True,
                "path": self.display_path(target),
                "entries": [self.entry(target)],
            }
        return {
            "ok": True,
            "path": self.display_path(target),
            "entries": await self.walk(target, depth),
        }

    async def walk(self, directory: Path, remaining: int) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for backend_entry in await self.backend.list_dir(str(directory)):
            child = directory / backend_entry.name
            item = self.entry(child)
            if backend_entry.is_dir and remaining > 1:
                item["children"] = await self.walk(child, remaining - 1)
            entries.append(item)
        return entries

    def entry(self, path: Path) -> dict[str, object]:
        is_dir = path.is_dir()
        return {
            "name": path.name,
            "path": self.display_path(path),
            "type": "dir" if is_dir else "file",
            "size": None if is_dir else path.stat().st_size,
        }

    async def copy_to_sandbox(
        self,
        source: str,
        sandbox: Sandbox,
        destination: str = ".",
    ) -> str:
        source_path = self.resolve(source, allow_missing=False)
        target = posixpath.join(
            sandbox.virtual_path(destination),
            source_path.name,
        )
        await self.copy_user_path_to_sandbox(source_path, sandbox, target)
        return target

    async def copy_user_path_to_sandbox(
        self,
        source: Path,
        sandbox: Sandbox,
        target: str,
    ) -> None:
        if source.is_file():
            await sandbox.files.write(target, await self.backend.read_file(str(source)))
            return
        for entry in await self.backend.list_dir(str(source)):
            await self.copy_user_path_to_sandbox(
                source / entry.name,
                sandbox,
                posixpath.join(target, entry.name),
            )

    async def copy_from_sandbox(
        self,
        sandbox: Sandbox,
        source: str,
        destination: str = ".",
    ) -> str:
        self.require_write()
        source_path = sandbox.resolve(source)
        source_name = os.path.basename(source_path.rstrip(os.sep))
        target = self.resolve(os.path.join(destination, source_name))
        await self.copy_sandbox_path_to_user(sandbox, source_path, target)
        return self.display_path(target)

    async def copy_sandbox_path_to_user(
        self,
        sandbox: Sandbox,
        source: str,
        target: Path,
    ) -> None:
        entries = None
        try:
            entries = await sandbox.backend.list_dir(source)
        except (NotADirectoryError, OSError):
            pass
        if entries is None:
            await self.backend.write_file(
                str(target),
                await sandbox.backend.read_file(source),
            )
            return
        for entry in entries:
            await self.copy_sandbox_path_to_user(
                sandbox,
                os.path.join(source, entry.name),
                target / entry.name,
            )

    def tools(self, sandbox: Sandbox | None = None):
        from .tools import build_userdir_tools

        return build_userdir_tools(self, sandbox)


def open_userdir(
    config: UserDirConfig,
    *,
    backend: UserDirBackend | None = None,
) -> UserDir | None:
    if config.access == "none":
        return None
    return UserDir(config, backend)
