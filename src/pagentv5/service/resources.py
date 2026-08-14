from __future__ import annotations

import asyncio
import posixpath
from collections.abc import AsyncIterator, Collection
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from ..events import RunnerEvent
from ..provider import ProviderInput
from ..runtime import Runner
from ..task import LocalTaskBackend, Task, TaskBackend, TaskSpec


class ResourceService:
    """Transport-neutral implementation of task resource endpoints."""

    def __init__(self, task_backend: TaskBackend | None = None) -> None:
        self.task_backend = task_backend or LocalTaskBackend()
        self.tasks: dict[str, Task] = {}
        self.run_tasks: dict[str, asyncio.Task[Any]] = {}

    async def create_task(
        self,
        spec: TaskSpec,
        *,
        task_id: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        selected_id = task_id or f"task-{uuid4().hex}"
        task = await self.task_backend.create(selected_id, spec)
        self.tasks[selected_id] = task
        if title:
            metadata = task.load_metadata()
            metadata["title"] = title
            self.task_backend.save_metadata(selected_id, metadata)
        return self.task_details(selected_id)

    async def open_task(self, task_id: str) -> dict[str, Any]:
        await self.get_task(task_id)
        return self.task_details(task_id)

    async def get_task(self, task_id: str) -> Task:
        existing = self.tasks.get(task_id)
        if existing is not None and not existing.closed:
            return existing
        task = await self.task_backend.open(task_id)
        self.tasks[task_id] = task
        return task

    async def release_task(self, task_id: str) -> None:
        task = self.tasks.pop(task_id, None)
        if task is not None:
            await task.close()

    def list_tasks(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        return [
            asdict(summary)
            for summary in self.task_backend.list(include_deleted=include_deleted)
        ]

    def task_details(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        if task is None:
            metadata = self.task_backend.metadata(task_id)
            summary = next(
                (
                    item
                    for item in self.task_backend.list(include_deleted=True)
                    if item.id == task_id
                ),
                None,
            )
            if summary is None:
                raise FileNotFoundError(f"task not found: {task_id}")
            return {"summary": asdict(summary), "metadata": metadata}
        return {
            "id": task.id,
            "root": str(task.root),
            "spec_path": str(task.spec_path),
            "spec": task.spec.to_dict(),
            "metadata": task.load_metadata(),
            "tool_names": task.tool_names(),
        }

    async def update_task_metadata(
        self,
        task_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        task = await self.get_task(task_id)
        metadata = task.load_metadata()
        metadata.update(updates)
        self.task_backend.save_metadata(task_id, metadata)
        return metadata

    async def delete_task(self, task_id: str) -> None:
        await self.release_task(task_id)
        self.task_backend.delete(task_id)

    async def session_messages(self, task_id: str) -> list[dict[str, Any]]:
        task = await self.get_task(task_id)
        return list(task.session.messages)

    async def replace_session(
        self,
        task_id: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        task = await self.get_task(task_id)
        task.session.replace(messages)
        return list(task.session.messages)

    async def clear_session(self, task_id: str) -> None:
        task = await self.get_task(task_id)
        task.session.clear()

    async def sandbox_status(self, task_id: str) -> dict[str, Any]:
        task = await self.get_task(task_id)
        sandbox = task.sandbox
        if sandbox is None:
            return {
                "task_id": task_id,
                "backend": "none",
                "alive": False,
                "workdir": None,
            }
        return {
            "task_id": task_id,
            "backend": task.spec.sandbox.backend,
            "alive": await sandbox.alive(),
            "workdir": sandbox.workdir,
            "home": sandbox.home,
        }

    async def sandbox_tree(
        self,
        task_id: str,
        *,
        path: str = ".",
        depth: int = 3,
    ) -> list[dict[str, Any]]:
        if depth < 1 or depth > 5:
            raise ValueError("depth must be 1..5")
        task = await self.get_task(task_id)
        if task.sandbox is None:
            return []
        virtual = task.sandbox.virtual_path(path)
        return await self.walk_sandbox(task, virtual, depth)

    async def walk_sandbox(
        self,
        task: Task,
        virtual_path: str,
        remaining: int,
    ) -> list[dict[str, Any]]:
        if task.sandbox is None:
            return []
        entries = await task.sandbox.files.list(virtual_path)
        nodes: list[dict[str, Any]] = []
        for entry in entries:
            child = posixpath.join(virtual_path, entry.name)
            node: dict[str, Any] = {
                "path": child,
                "name": entry.name,
                "type": "dir" if entry.is_dir else "file",
                "size": entry.size,
            }
            if entry.is_dir and remaining > 1:
                node["children"] = await self.walk_sandbox(
                    task,
                    child,
                    remaining - 1,
                )
            nodes.append(node)
        return nodes

    async def read_sandbox_file(self, task_id: str, path: str) -> bytes:
        task = await self.get_task(task_id)
        if task.sandbox is None:
            raise FileNotFoundError(f"task {task_id!r} has no sandbox")
        return await task.sandbox.files.read(path)

    async def userdir_status(self, task_id: str) -> dict[str, Any]:
        task = await self.get_task(task_id)
        if task.userdir is None:
            return {"task_id": task_id, "access": "none", "path": None}
        return {
            "task_id": task_id,
            "access": task.userdir.access,
            "path": str(task.userdir.root),
        }

    async def userdir_tree(
        self,
        task_id: str,
        *,
        path: str = "",
        depth: int = 3,
    ) -> dict[str, object]:
        task = await self.get_task(task_id)
        if task.userdir is None:
            return {"ok": True, "path": ".", "entries": []}
        return await task.userdir.list(path, depth=depth)

    async def read_userdir_file(self, task_id: str, path: str) -> bytes:
        task = await self.get_task(task_id)
        if task.userdir is None:
            raise FileNotFoundError(f"task {task_id!r} has no user directory")
        return await task.userdir.read(path)

    async def capabilities(self, task_id: str) -> dict[str, Any]:
        task = await self.get_task(task_id)
        return {
            "task_id": task_id,
            "provider": task.spec.provider.name,
            "model_id": task.spec.provider.model_id,
            "tool_names": task.tool_names(),
            "sandbox_backend": task.spec.sandbox.backend,
            "userdir_access": task.spec.userdir.access,
            "session_storage": task.spec.session.storage,
        }

    async def run(
        self,
        task_id: str,
        input: ProviderInput,
        *,
        api_key: str | None = None,
        event_types: Collection[str] | None = None,
        **request_kwargs: Any,
    ) -> AsyncIterator[RunnerEvent]:
        task = await self.get_task(task_id)
        if task_id in self.run_tasks:
            raise RuntimeError(f"task {task_id!r} already has a run in progress")

        runner = Runner(
            task.create_provider(api_key=api_key),
            tools=task.tools(),
            event_types=event_types,
            session=task.session,
        )
        current = asyncio.current_task()
        if current is not None:
            self.run_tasks[task_id] = current
        try:
            async for event in runner.run(input, **request_kwargs):
                yield event
        finally:
            self.run_tasks.pop(task_id, None)

    def cancel_run(self, task_id: str) -> bool:
        run_task = self.run_tasks.get(task_id)
        if run_task is None:
            return False
        run_task.cancel()
        return True

    async def close(self) -> None:
        for task_id in list(self.tasks):
            await self.release_task(task_id)
