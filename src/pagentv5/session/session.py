from __future__ import annotations

from pathlib import Path
from types import TracebackType

from ..paths import default_pagent_home
from .backends import (
    JsonlSessionBackend,
    MemorySessionBackend,
    SqliteSessionBackend,
)
from .config import SessionConfig
from .protocol import SessionBackend, SessionMessage


def resolve_path(path: str, base_path: Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_path / candidate).resolve()


def create_session_backend(
    config: SessionConfig,
    *,
    base_path: str | Path | None = None,
) -> SessionBackend:
    base = (
        Path(base_path).expanduser().resolve()
        if base_path is not None
        else default_pagent_home()
    )
    if config.storage == "memory":
        return MemorySessionBackend()
    if config.storage == "jsonl":
        return JsonlSessionBackend(resolve_path(config.root, base))
    return SqliteSessionBackend(resolve_path(config.database, base))


class Session:
    def __init__(
        self,
        session_id: str,
        backend: SessionBackend,
    ) -> None:
        self.id = session_id
        self.backend = backend
        self.messages = backend.load(session_id)
        self.closed = False

    @classmethod
    def open(
        cls,
        config: SessionConfig,
        *,
        base_path: str | Path | None = None,
        backend: SessionBackend | None = None,
    ) -> Session:
        return cls(
            config.session_id,
            backend or create_session_backend(config, base_path=base_path),
        )

    def reload(self) -> list[SessionMessage]:
        self.require_open()
        self.messages = self.backend.load(self.id)
        return list(self.messages)

    def save(self) -> None:
        self.require_open()
        self.backend.save(self.id, self.messages)

    def replace(self, messages: list[SessionMessage]) -> None:
        self.require_open()
        self.messages = list(messages)
        self.save()

    def append(self, message: SessionMessage) -> None:
        self.require_open()
        self.messages.append(dict(message))
        self.save()

    def extend(self, messages: list[SessionMessage]) -> None:
        self.require_open()
        self.messages.extend(dict(message) for message in messages)
        self.save()

    def clear(self) -> None:
        self.replace([])

    def delete(self) -> None:
        self.require_open()
        self.backend.delete(self.id)
        self.messages = []

    def require_open(self) -> None:
        if self.closed:
            raise RuntimeError("session is closed")

    def close(self) -> None:
        if self.closed:
            return
        self.backend.close()
        self.closed = True

    def __enter__(self) -> Session:
        self.require_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
