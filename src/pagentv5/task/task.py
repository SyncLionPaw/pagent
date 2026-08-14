from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType

from ..provider import Provider
from ..sandbox import Sandbox
from ..session import Session
from ..tools import FunctionTool
from ..userdir import UserDir, compose_tools
from .config import TaskSpec


class Task:
    def __init__(
        self,
        task_id: str,
        root: Path,
        spec_path: Path,
        spec: TaskSpec,
        *,
        session: Session,
        userdir: UserDir | None,
        sandbox: Sandbox | None,
    ) -> None:
        self.id = task_id
        self.root = root
        self.spec_path = spec_path
        self.spec = spec
        self.session = session
        self.userdir = userdir
        self.sandbox = sandbox
        self.closed = False

    @property
    def workspace_path(self) -> Path | None:
        if self.spec.sandbox.backend == "none":
            return None
        return self.root / "workspaces" / "main"

    @property
    def metadata_path(self) -> Path:
        return self.root / "metainfo.json"

    def create_provider(self, *, api_key: str | None = None) -> Provider:
        return self.spec.provider.create_provider(api_key=api_key)

    def tool_names(self) -> list[str]:
        return compose_tools(self.spec.sandbox, self.spec.userdir)

    def tools(self) -> list[FunctionTool]:
        tools: list[FunctionTool] = []
        if self.sandbox is not None:
            tools.extend(self.sandbox.tools())
        if self.userdir is not None:
            tools.extend(self.userdir.tools(self.sandbox))
        return tools

    def load_metadata(self) -> dict:
        if not self.metadata_path.exists():
            return {}
        with self.metadata_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save_metadata(self, metadata: dict) -> None:
        self.metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    async def close(self) -> None:
        if self.closed:
            return
        if self.sandbox is not None:
            await self.sandbox.close()
        self.session.close()
        self.closed = True

    async def __aenter__(self) -> Task:
        if self.closed:
            raise RuntimeError("task is closed")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
