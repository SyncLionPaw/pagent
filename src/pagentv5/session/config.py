from dataclasses import dataclass
from typing import Literal, TypeAlias

SessionStorage: TypeAlias = Literal["memory", "jsonl", "sqlite"]


@dataclass(frozen=True, slots=True)
class SessionConfig:
    storage: SessionStorage = "jsonl"
    session_id: str = "messages"
    root: str = "sessions"
    database: str = "sessions.sqlite"

    def __post_init__(self) -> None:
        if self.storage not in {"memory", "jsonl", "sqlite"}:
            raise ValueError(f"unknown session storage: {self.storage!r}")
