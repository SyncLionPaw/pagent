from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .config import TaskSpec
    from .task import Task


@dataclass(frozen=True, slots=True)
class TaskSummary:
    id: str
    title: str
    updated_at: str
    userdir_path: str | None
    sandbox_backend: str
    deleted: bool = False


@runtime_checkable
class TaskBackend(Protocol):
    root: Path

    async def create(self, task_id: str, spec: TaskSpec) -> Task: ...
    async def open(self, task_id: str) -> Task: ...
    def list(self, *, include_deleted: bool = False) -> list[TaskSummary]: ...
    def metadata(self, task_id: str) -> dict: ...
    def save_metadata(self, task_id: str, metadata: dict) -> None: ...
    def delete(self, task_id: str) -> None: ...
