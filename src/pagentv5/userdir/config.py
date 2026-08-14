from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

UserDirAccess: TypeAlias = Literal["none", "readonly", "readwrite"]


@dataclass(frozen=True, slots=True)
class UserDirConfig:
    access: UserDirAccess = "none"
    path: str | None = None

    def __post_init__(self) -> None:
        if self.access not in {"none", "readonly", "readwrite"}:
            raise ValueError(f"unknown user directory access: {self.access!r}")
        if self.access == "none":
            return
        if self.path is None or not self.path.strip():
            raise ValueError(f"user directory path is required for {self.access}")
        resolved = Path(self.path).expanduser().resolve()
        if not resolved.is_dir():
            raise ValueError(f"user directory is not a directory: {resolved}")

    @property
    def root(self) -> Path | None:
        if self.access == "none" or self.path is None:
            return None
        return Path(self.path).expanduser().resolve()
