from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator, Collection
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, TypeAlias

from ..events import RunnerEvent, TextDeltaEvent
from ..provider import Provider, ProviderInput, ProviderProtocol
from ..runtime import Runner, ToolApproval
from ..sandbox import DockerBackend, PodmanBackend, Sandbox, SandboxConfig
from ..tools import FunctionTool
from ..userdir import UserDir, UserDirConfig

EmitType: TypeAlias = Literal["event", "text"]
SdkOutput: TypeAlias = RunnerEvent | str


def resolve_max_turns(
    max_turns: int | None,
    max_turn: int | None,
) -> int:
    if max_turns is not None and max_turn is not None:
        raise TypeError("pass max_turns or max_turn, not both")
    selected = max_turns if max_turns is not None else max_turn
    return 24 if selected is None else selected


def validate_emit_type(emit_type: str) -> EmitType:
    if emit_type not in {"event", "text"}:
        raise ValueError("emit_type must be 'event' or 'text'")
    return emit_type


def parse_sandbox(
    value: str,
) -> tuple[Literal["local", "container", "ssh"], str | None, str | None]:
    if value == "local":
        return "local", None, None
    if value == "ssh":
        return "ssh", None, None
    if not value.startswith("container:"):
        raise ValueError(
            "sandbox must be 'local', 'ssh', 'container:<image>', or "
            "'container:<docker|podman>:<image>'"
        )

    payload = value.removeprefix("container:")
    runtime, separator, image = payload.partition(":")
    if runtime in {"docker", "podman"}:
        if not separator or not image:
            raise ValueError("container sandbox requires an image")
        return "container", image, runtime
    if not payload:
        raise ValueError("container sandbox requires an image")
    return "container", payload, None


class BaseAgent(Runner):
    """Stateful Runner with convenient Provider construction and output projection."""

    def __init__(
        self,
        model_id: str,
        *,
        provider_id: str | None = "deepseek",
        api_protocol: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        provider: ProviderProtocol | None = None,
        tools: list[FunctionTool] | None = None,
        system: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        max_turns: int | None = None,
        max_turn: int | None = None,
        yolo: bool = False,
        approve_tool: ToolApproval | None = None,
        emit_type: EmitType = "event",
        request_kwargs: dict[str, Any] | None = None,
        max_retries: int | None = None,
    ) -> None:
        selected_provider = provider or Provider(
            model_id,
            provider_id=provider_id,
            api_protocol=api_protocol,
            base_url=base_url,
            api_key=api_key,
            request_kwargs=request_kwargs,
            max_retries=max_retries,
        )
        self.custom_tools = list(tools or [])
        self.messages = [dict(message) for message in messages or []]
        existing_system = next(
            (
                message.get("content")
                for message in self.messages
                if message.get("role") == "system"
                and isinstance(message.get("content"), str)
            ),
            None,
        )
        self.system = system or existing_system
        if system and not any(
            message.get("role") == "system" for message in self.messages
        ):
            self.messages.insert(0, {"role": "system", "content": system})
        selected_max_turns = resolve_max_turns(max_turns, max_turn)
        self.yolo = yolo
        self.emit_type = validate_emit_type(emit_type)
        self.closed = False
        super().__init__(
            selected_provider,
            tools=self.custom_tools,
            max_turns=selected_max_turns,
            require_tool_approval=not yolo,
            approve_tool=approve_tool,
        )

    async def initialize(self) -> None:
        self.require_open()

    def build_input(self, input: ProviderInput) -> list[dict[str, Any]]:
        messages = [dict(message) for message in self.messages]
        if isinstance(input, str):
            messages.append({"role": "user", "content": input})
        else:
            messages.extend(dict(message) for message in input)
        return messages

    async def run(
        self,
        input: ProviderInput,
        *,
        emit_type: EmitType | None = None,
        event_types: Collection[str] | None = None,
        **request_kwargs: Any,
    ) -> AsyncIterator[SdkOutput]:
        await self.initialize()

        selected_emit_type = validate_emit_type(emit_type or self.emit_type)
        messages = self.build_input(input)
        try:
            async for event in super().run(messages, **request_kwargs):
                if event_types is not None and event.type not in event_types:
                    continue
                if selected_emit_type == "event":
                    yield event
                elif isinstance(event, TextDeltaEvent):
                    yield event.delta
        finally:
            if isinstance(self.last_input, list):
                self.messages = [dict(message) for message in self.last_input]

    async def ask(
        self,
        input: ProviderInput,
        **request_kwargs: Any,
    ) -> str:
        return "".join(
            [
                chunk
                async for chunk in self.run(
                    input,
                    emit_type="text",
                    **request_kwargs,
                )
                if isinstance(chunk, str)
            ]
        )

    def clear(self) -> None:
        self.require_open()
        self.messages = []
        if self.system:
            self.messages.append({"role": "system", "content": self.system})

    def require_open(self) -> None:
        if self.closed:
            raise RuntimeError("agent is closed")

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> BaseAgent:
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()


class SandboxWorker(BaseAgent):
    """Agent with an owned sandbox work root."""

    def __init__(
        self,
        model_id: str,
        *,
        workspace_path: str | Path | None = None,
        sandbox: str | None = None,
        sandbox_backend: Literal["local", "container", "ssh"] = "local",
        sandbox_image: str | None = None,
        sandbox_connection: dict[str, str] | None = None,
        command_policy: Literal["open", "workdir"] = "workdir",
        **kwargs: Any,
    ) -> None:
        super().__init__(model_id, **kwargs)
        sandbox_runtime = None
        if sandbox is not None:
            sandbox_backend, sandbox_image, sandbox_runtime = parse_sandbox(sandbox)
        self.workspace_path = (
            Path(workspace_path).expanduser().resolve()
            if workspace_path is not None
            else None
        )
        self.sandbox_config = SandboxConfig(
            backend=sandbox_backend,
            image=sandbox_image,
            connection=dict(sandbox_connection or {}),
            command_policy=command_policy,
        )
        self.sandbox_runtime = sandbox_runtime
        self.sandbox: Sandbox | None = None
        self.temporary_workspace: tempfile.TemporaryDirectory[str] | None = None

    async def initialize(self) -> None:
        self.require_open()
        if self.sandbox is None:
            if self.workspace_path is None:
                self.temporary_workspace = tempfile.TemporaryDirectory(
                    prefix="pagentv5-sandbox-"
                )
                self.workspace_path = Path(self.temporary_workspace.name)
            try:
                backend = None
                if self.sandbox_runtime == "docker":
                    backend = DockerBackend()
                elif self.sandbox_runtime == "podman":
                    backend = PodmanBackend()
                self.sandbox = await Sandbox.open(
                    self.sandbox_config,
                    self.workspace_path,
                    backend=backend,
                )
            except Exception:
                if self.temporary_workspace is not None:
                    self.temporary_workspace.cleanup()
                    self.temporary_workspace = None
                    self.workspace_path = None
                raise
            self.set_tools(self.build_tools())
        await super().initialize()

    def build_tools(self) -> list[FunctionTool]:
        if self.sandbox is None:
            raise RuntimeError("sandbox is not initialized")
        return [*self.custom_tools, *self.sandbox.tools()]

    async def close(self) -> None:
        if self.closed:
            return
        if self.sandbox is not None:
            await self.sandbox.close()
        if self.temporary_workspace is not None:
            self.temporary_workspace.cleanup()
            self.temporary_workspace = None
        await super().close()


class LocalCodeAgent(BaseAgent):
    """Agent that directly uses a local project directory as its work root."""

    def __init__(
        self,
        model_id: str,
        *,
        project_path: str | Path,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_id, **kwargs)
        self.project_path = Path(project_path).expanduser().resolve()
        self.userdir = UserDir(
            UserDirConfig(
                access="readwrite",
                path=str(self.project_path),
            )
        )
        self.set_tools(self.build_tools())

    def build_tools(self) -> list[FunctionTool]:
        return [*self.custom_tools, *self.userdir.tools()]


SandBoxWorker = SandboxWorker
