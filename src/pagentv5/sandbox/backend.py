from .config import SandboxConfig
from .container import DockerBackend, PodmanBackend
from .guard import BackendGuard
from .local import LocalBackend
from .protocol import SandboxBackend
from .util import detect_container_cli


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
        from .ssh import SshBackend

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
