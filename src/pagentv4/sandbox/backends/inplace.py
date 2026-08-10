"""InplaceBackend - run commands and edit the bound project directly."""

from __future__ import annotations

from ..base import BackendIdentity, SandboxSpec
from .local import LocalBackend


class InplaceBackend(LocalBackend):
    def describe(self, spec: SandboxSpec, workdir: str) -> BackendIdentity:
        home = spec.home
        return BackendIdentity(
            computer_name="本地项目",
            extra=(
                f"当前项目目录：{workdir}\n"
                f"run_command 的 shell 工作目录：{workdir}\n"
                f"文件工具路径 {home} 直接映射到当前项目。\n"
                "文件修改会立即写入项目，无需复制或另行交付。\n"
            ),
        )
