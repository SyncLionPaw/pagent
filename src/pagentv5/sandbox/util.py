from __future__ import annotations

import os
import shutil

from .error import SandboxError

CONTAINER_CLI_PREFERENCE = ("docker", "podman")


def detect_container_cli() -> str:
    for cli in CONTAINER_CLI_PREFERENCE:
        if shutil.which(cli):
            return cli
    joined = " / ".join(CONTAINER_CLI_PREFERENCE)
    raise SandboxError(f"no container CLI found in PATH; install one of: {joined}")


def under_root(path: str, root: str) -> bool:
    root_norm = os.path.normpath(root)
    path_norm = os.path.normpath(path)
    return path_norm == root_norm or path_norm.startswith(root_norm + os.sep)


def check_backend_path(path: str, *, workdir: str) -> None:
    if not under_root(path, workdir):
        raise PermissionError(
            f"backend path escapes workspace: {path!r} "
            f"(workspace is {os.path.normpath(workdir)!r})"
        )
