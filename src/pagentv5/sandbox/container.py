import asyncio
import os
import shutil

from pagentv4.sandbox.backends.container import ContainerBackend as V4ContainerBackend

from .protocol import SandboxError, SandboxSpec


class ContainerBackend(V4ContainerBackend):
    def __init__(
        self,
        cli: str,
        computer_name: str,
        *,
        bind_mounts: tuple[str, ...] = (),
    ) -> None:
        super().__init__(cli=cli, computer_name=computer_name)
        self.bind_mounts = tuple(
            str(os.path.abspath(os.path.expanduser(path))) for path in bind_mounts
        )

    async def start(self, spec: SandboxSpec, workdir: str) -> None:
        if not spec.image:
            raise ValueError(f"{self.cli} backend requires image")
        if shutil.which(self.cli) is None:
            raise SandboxError(f"{self.cli} CLI not found in PATH")

        os.makedirs(workdir, exist_ok=True)
        self.spec = spec
        self.workdir = workdir

        mounts = tuple(dict.fromkeys((workdir, *self.bind_mounts)))
        argv: list[str] = [self.cli, "run", "-d", "--rm"]
        for mount in mounts:
            if not os.path.isdir(mount):
                raise ValueError(f"container bind mount is not a directory: {mount}")
            argv.extend(["-v", f"{mount}:{mount}"])
        argv.extend(["-w", workdir])
        for key, value in spec.env.items():
            argv.extend(["--env", f"{key}={value}"])
        if spec.command:
            argv.append(spec.image)
            argv.extend(spec.command)
        else:
            ttl = spec.container_ttl_seconds
            argv.extend(
                [spec.image, "sleep", str(ttl) if ttl is not None else "infinity"]
            )

        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise SandboxError(f"{self.cli} run failed: {detail}")
        self.container_id = stdout.decode("utf-8", errors="replace").strip()


class DockerBackend(ContainerBackend):
    def __init__(self, *, bind_mounts: tuple[str, ...] = ()) -> None:
        super().__init__(
            "docker",
            "Docker backend",
            bind_mounts=bind_mounts,
        )


class PodmanBackend(ContainerBackend):
    def __init__(self, *, bind_mounts: tuple[str, ...] = ()) -> None:
        super().__init__(
            "podman",
            "Podman backend",
            bind_mounts=bind_mounts,
        )
