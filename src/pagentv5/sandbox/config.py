from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from .protocol import SandboxLimits

SandboxBackendName: TypeAlias = Literal["none", "local", "container", "ssh"]


@dataclass(frozen=True, slots=True)
class SandboxConfig:
    backend: SandboxBackendName = "local"
    home: str = "/home/agent"
    image: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    connection: dict[str, str] = field(default_factory=dict)
    default_limits: SandboxLimits = field(default_factory=SandboxLimits)
    container_ttl_seconds: int | None = None
    auto_restart: bool = True
    restart_max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.backend not in {"none", "local", "container", "ssh"}:
            raise ValueError(f"unknown sandbox backend: {self.backend!r}")
        if not self.home.startswith("/"):
            raise ValueError("sandbox home must be an absolute virtual path")
        if self.backend == "container" and not self.image:
            raise ValueError("container sandbox requires image")
        if self.backend == "ssh":
            if not self.connection.get("host") or not self.connection.get("user"):
                raise ValueError("ssh sandbox requires connection host and user")
