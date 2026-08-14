from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from pagentv4.paths import default_pagent_home

from ..sandbox import Sandbox
from ..session import Session
from ..userdir import open_userdir
from .config import TaskSpec
from .protocol import TaskSummary
from .task import Task
from .toml import dump_task_toml, load_task_toml

TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$")
TASK_SPEC_FILENAME = "task.toml"
TASK_METADATA_FILENAME = "metainfo.json"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_task_id(task_id: str) -> None:
    if TASK_ID_PATTERN.fullmatch(task_id):
        return
    raise ValueError(
        f"invalid task_id: {task_id!r}; must match [A-Za-z0-9][A-Za-z0-9_.-]{{0,127}}"
    )


def default_tasks_root() -> Path:
    return default_pagent_home() / "tasks"


class LocalTaskBackend:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = (
            Path(root).expanduser().resolve()
            if root is not None
            else default_tasks_root()
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def task_path(self, task_id: str) -> Path:
        validate_task_id(task_id)
        return self.root / task_id

    async def create(self, task_id: str, spec: TaskSpec) -> Task:
        task_root = self.task_path(task_id)
        spec_path = task_root / TASK_SPEC_FILENAME
        if spec_path.exists():
            raise FileExistsError(f"task already exists: {task_id}")

        task_root.mkdir(parents=True, exist_ok=False)
        locked_spec = spec.with_lock(str(spec_path.resolve()))
        self.write_spec(spec_path, locked_spec)
        now = utc_now()
        self.save_metadata(
            task_id,
            {
                "title": task_id,
                "created_at": now,
                "updated_at": now,
                "deleted": False,
            },
        )
        return await self.open(task_id)

    async def open(self, task_id: str) -> Task:
        task_root = self.task_path(task_id)
        spec_path = task_root / TASK_SPEC_FILENAME
        if not spec_path.exists():
            raise FileNotFoundError(f"task not found: {task_id}")
        metadata = self.metadata(task_id)
        if metadata.get("deleted"):
            raise FileNotFoundError(f"task is deleted: {task_id}")

        payload = load_task_toml(spec_path)
        spec = TaskSpec.from_dict(payload)
        expected_path = str(spec_path.resolve())
        if spec.file_self_fs_pos and spec.file_self_fs_pos != expected_path:
            raise ValueError(
                f"task lock path mismatch: {spec.file_self_fs_pos!r} != {expected_path!r}"
            )
        sandbox_payload = payload.get("sandbox", {})
        needs_migration = (
            "compute" in sandbox_payload or "command_policy" in sandbox_payload
        )
        if not spec.file_self_fs_pos or needs_migration:
            spec = spec.with_lock(expected_path)
            self.write_spec(spec_path, spec)

        session = Session.open(spec.session, base_path=task_root)
        userdir = open_userdir(spec.userdir)
        sandbox = None
        try:
            if spec.sandbox.backend != "none":
                workspace = task_root / "workspaces" / "main"
                bind_mounts: tuple[str, ...] = ()
                if (
                    spec.sandbox.backend == "container"
                    and spec.userdir.access == "readwrite"
                    and spec.userdir.root is not None
                ):
                    bind_mounts = (str(spec.userdir.root),)
                sandbox = await Sandbox.open(
                    spec.sandbox,
                    workspace,
                    bind_mounts=bind_mounts,
                )
        except Exception:
            session.close()
            raise

        return Task(
            task_id,
            task_root,
            spec_path,
            spec,
            session=session,
            userdir=userdir,
            sandbox=sandbox,
        )

    def write_spec(self, path: Path, spec: TaskSpec) -> None:
        temporary = path.with_suffix(".toml.tmp")
        temporary.write_text(
            dump_task_toml(spec.to_dict()),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def metadata(self, task_id: str) -> dict:
        path = self.task_path(task_id) / TASK_METADATA_FILENAME
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save_metadata(self, task_id: str, metadata: dict) -> None:
        task_root = self.task_path(task_id)
        if not task_root.exists():
            raise FileNotFoundError(f"task not found: {task_id}")
        path = task_root / TASK_METADATA_FILENAME
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)

    def list(self, *, include_deleted: bool = False) -> list[TaskSummary]:
        summaries: list[TaskSummary] = []
        for task_root in self.root.iterdir():
            spec_path = task_root / TASK_SPEC_FILENAME
            if not task_root.is_dir() or not spec_path.exists():
                continue
            metadata = self.metadata(task_root.name)
            deleted = bool(metadata.get("deleted", False))
            if deleted and not include_deleted:
                continue
            payload = load_task_toml(spec_path)
            userdir = payload.get("userdir", {})
            sandbox = payload.get("sandbox", {})
            summaries.append(
                TaskSummary(
                    id=task_root.name,
                    title=str(metadata.get("title") or task_root.name),
                    updated_at=str(metadata.get("updated_at") or ""),
                    userdir_path=userdir.get("path"),
                    sandbox_backend=str(
                        sandbox.get(
                            "backend",
                            sandbox.get("compute", "local"),
                        )
                    ),
                    deleted=deleted,
                )
            )
        return sorted(
            summaries,
            key=lambda summary: (summary.updated_at, summary.id),
            reverse=True,
        )

    def delete(self, task_id: str) -> None:
        metadata = self.metadata(task_id)
        if not metadata and not self.task_path(task_id).exists():
            raise FileNotFoundError(f"task not found: {task_id}")
        now = utc_now()
        metadata.update(
            {
                "deleted": True,
                "deleted_at": now,
                "updated_at": now,
            }
        )
        self.save_metadata(task_id, metadata)
