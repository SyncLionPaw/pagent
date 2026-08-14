import shutil

from pagentv4.sandbox.backends.local import LocalBackend
from pagentv4.sandbox.guard import BackendGuard

from .config import SandboxConfig
from .container import DockerBackend, PodmanBackend
from .protocol import SandboxBackend, SandboxError

CONTAINER_CLI_PREFERENCE = ("docker", "podman")


def detect_container_cli() -> str:
    for cli in CONTAINER_CLI_PREFERENCE:
        if shutil.which(cli):
            return cli
    joined = " / ".join(CONTAINER_CLI_PREFERENCE)
    raise SandboxError(f"no container CLI found in PATH; install one of: {joined}")


def create_backend(
    config: SandboxConfig,
    *,
    bind_mounts: tuple[str, ...] = (),
) -> SandboxBackend:
    if config.backend == "none":
        raise ValueError("sandbox backend 'none' has no implementation")
    if config.backend == "local":
        backend: SandboxBackend = LocalBackend()
    elif config.backend == "ssh":
        from pagentv4.sandbox.backends.ssh import SshBackend

        backend = SshBackend()
    else:
        cli = detect_container_cli()
        backend = (
            DockerBackend(bind_mounts=bind_mounts)
            if cli == "docker"
            else PodmanBackend(bind_mounts=bind_mounts)
        )

    if not config.auto_restart:
        return backend
    return BackendGuard(
        backend,
        restart_max_attempts=config.restart_max_attempts,
    )
