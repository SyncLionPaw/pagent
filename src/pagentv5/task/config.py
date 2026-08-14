from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..provider import Provider
from ..sandbox import SandboxConfig, SandboxLimits
from ..session import SessionConfig
from ..userdir import UserDirConfig, validate_resource_combination

TASK_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    name: str = "default"
    model_id: str = "deepseek-v4-flash"
    provider_id: str | None = "deepseek"
    api_protocol: str | None = None
    base_url: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("provider binding name must not be empty")
        if not self.model_id.strip():
            raise ValueError("provider model_id must not be empty")

    def create_provider(self, *, api_key: str | None = None) -> Provider:
        return Provider(
            self.model_id,
            provider_id=self.provider_id,
            api_protocol=self.api_protocol,
            base_url=self.base_url,
            api_key=api_key,
        )


@dataclass(frozen=True, slots=True)
class TaskSpec:
    provider: ProviderBinding = field(default_factory=ProviderBinding)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    userdir: UserDirConfig = field(default_factory=UserDirConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    schema_version: int = TASK_SCHEMA_VERSION
    file_self_fs_pos: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_resource_combination(self.sandbox, self.userdir)
        if self.schema_version < 1:
            raise ValueError("task schema_version must be >= 1")

    def with_lock(self, file_self_fs_pos: str) -> TaskSpec:
        return TaskSpec(
            provider=self.provider,
            sandbox=self.sandbox,
            userdir=self.userdir,
            session=self.session,
            schema_version=TASK_SCHEMA_VERSION,
            file_self_fs_pos=file_self_fs_pos,
            extra=dict(self.extra),
        )

    def to_dict(self) -> dict[str, Any]:
        limits = self.sandbox.default_limits
        return {
            "provider": {
                "name": self.provider.name,
                "model_id": self.provider.model_id,
                "provider_id": self.provider.provider_id,
                "api_protocol": self.provider.api_protocol,
                "base_url": self.provider.base_url,
            },
            "sandbox": {
                "backend": self.sandbox.backend,
                "home": self.sandbox.home,
                "image": self.sandbox.image,
                "container_ttl_seconds": self.sandbox.container_ttl_seconds,
                "command_policy": self.sandbox.command_policy,
                "auto_restart": self.sandbox.auto_restart,
                "restart_max_attempts": self.sandbox.restart_max_attempts,
                "env": dict(self.sandbox.env),
                "connection": dict(self.sandbox.connection),
                "limits": {
                    "timeout": limits.timeout,
                    "stdout_bytes": limits.stdout_bytes,
                    "stderr_bytes": limits.stderr_bytes,
                    "memory_bytes": limits.memory_bytes,
                    "cpu_seconds": limits.cpu_seconds,
                },
            },
            "userdir": {
                "access": self.userdir.access,
                "path": self.userdir.path,
            },
            "session": {
                "storage": self.session.storage,
                "session_id": self.session.session_id,
                "root": self.session.root,
                "database": self.session.database,
            },
            "lock": {
                "schema_version": self.schema_version,
                "file_self_fs_pos": self.file_self_fs_pos,
            },
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TaskSpec:
        provider = payload.get("provider", {})
        provider_id = provider.get("provider_id")
        if (
            "provider_id" not in provider
            and not provider.get("api_protocol")
            and not provider.get("base_url")
        ):
            provider_id = "deepseek"
        sandbox = payload.get("sandbox", {})
        limits = sandbox.get("limits", {})
        userdir = payload.get("userdir", {})
        session = payload.get("session", {})
        lock = payload.get("lock", {})
        return cls(
            provider=ProviderBinding(
                name=provider.get("name", "default"),
                model_id=provider.get("model_id", "deepseek-v4-flash"),
                provider_id=provider_id,
                api_protocol=provider.get("api_protocol"),
                base_url=provider.get("base_url"),
            ),
            sandbox=SandboxConfig(
                backend=sandbox.get(
                    "backend",
                    sandbox.get("compute", "local"),
                ),
                home=sandbox.get("home", "/home/agent"),
                image=sandbox.get("image"),
                env=dict(sandbox.get("env", {})),
                connection=dict(sandbox.get("connection", {})),
                default_limits=SandboxLimits(
                    timeout=limits.get("timeout"),
                    stdout_bytes=limits.get("stdout_bytes", 1024 * 1024),
                    stderr_bytes=limits.get("stderr_bytes", 256 * 1024),
                    memory_bytes=limits.get("memory_bytes"),
                    cpu_seconds=limits.get("cpu_seconds"),
                ),
                container_ttl_seconds=sandbox.get("container_ttl_seconds"),
                command_policy=sandbox.get("command_policy", "workdir"),
                auto_restart=sandbox.get("auto_restart", True),
                restart_max_attempts=sandbox.get("restart_max_attempts", 2),
            ),
            userdir=UserDirConfig(
                access=userdir.get("access", "none"),
                path=userdir.get("path"),
            ),
            session=SessionConfig(
                storage=session.get("storage", "jsonl"),
                session_id=session.get("session_id", "messages"),
                root=session.get("root", "sessions"),
                database=session.get("database", "sessions.sqlite"),
            ),
            schema_version=lock.get("schema_version", TASK_SCHEMA_VERSION),
            file_self_fs_pos=lock.get("file_self_fs_pos", ""),
            extra=dict(payload.get("extra", {})),
        )
