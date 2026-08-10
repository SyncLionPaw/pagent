"""Install and run pagentv4 inside Harbor task containers."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path, PurePosixPath
from typing import override

from harbor.agents.installed.base import BaseInstalledAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

REMOTE_VENV = PurePosixPath("/opt/pagent-venv")
REMOTE_WHEEL = PurePosixPath("/installed-agent/pagent.whl")
REMOTE_RUNNER = PurePosixPath("/installed-agent/pagent_local_runner.py")
REMOTE_INSTRUCTION = PurePosixPath("/installed-agent/instruction.txt")
REMOTE_LOGS = PurePosixPath("/logs/agent")

FORWARDED_ENV_VARS = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "MIMO_API_KEY",
    "LONGCAT_API_KEY",
    "OLLAMA_API_KEY",
    "VLLM_API_KEY",
    "SGLANG_API_KEY",
    "PAGENT_BENCH_API_KEY",
    "PAGENT_BENCH_BASE_URL",
)


class PagentV4Agent(BaseInstalledAgent):
    """Run pagentv4 Runner and LocalBackend inside the task container."""

    def __init__(
        self,
        *args,
        max_turns: int | str = 100,
        base_url: str | None = None,
        python_version: str = "3.12",
        source_root: str | Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.max_turns = int(max_turns)
        self.base_url = base_url
        self.python_version = python_version
        self.source_root = Path(source_root or Path(__file__).parents[2]).resolve()

    @staticmethod
    @override
    def name() -> str:
        return "pagentv4"

    @override
    def get_version_command(self) -> str:
        return (
            f"{REMOTE_VENV}/bin/python -c "
            "'import importlib.metadata; print(importlib.metadata.version(\"pagent\"))'"
        )

    def build_wheel(self) -> Path:
        wheel_dir = self.logs_dir / "setup" / "wheel"
        wheel_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
            cwd=self.source_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "uv build failed")
        wheels = list(wheel_dir.glob("pagent-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one pagent wheel, found {len(wheels)}")
        return wheels[0]

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        await self.ensure_system_dependencies(environment, ("curl", "coreutils"))

        wheel = self.build_wheel()
        runner = self.source_root / "examples" / "eval" / "pagent_local_runner.py"
        await environment.upload_file(wheel, REMOTE_WHEEL.as_posix())
        await environment.upload_file(runner, REMOTE_RUNNER.as_posix())

        await self.exec_as_root(
            environment,
            command=f"mkdir -p {REMOTE_VENV} && chmod 0777 {REMOTE_VENV}",
        )
        version = shlex.quote(self.python_version)
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "curl -LsSf https://astral.sh/uv/install.sh | sh; "
                'if [ -f "$HOME/.local/bin/env" ]; then . "$HOME/.local/bin/env"; fi; '
                f"uv python install {version}; "
                f"uv venv {REMOTE_VENV} --python {version} --clear; "
                f"uv pip install --python {REMOTE_VENV}/bin/python {REMOTE_WHEEL}"
            ),
            timeout_sec=600,
        )

    def build_agent_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        for name in FORWARDED_ENV_VARS:
            value = self._get_env(name)
            if value:
                env[name] = value
        if self.base_url:
            env["PAGENT_BENCH_BASE_URL"] = self.base_url
        return env

    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        del context
        if not self.model_name:
            raise ValueError("PagentV4Agent requires Harbor's --model option")

        instruction_path = self.logs_dir / "instruction.txt"
        instruction_path.write_text(instruction)
        await environment.upload_file(
            instruction_path,
            REMOTE_INSTRUCTION.as_posix(),
        )

        workdir = environment.task_env_config.workdir
        if not workdir:
            result = await environment.exec("pwd")
            if result.return_code != 0:
                raise RuntimeError(result.stderr or "failed to determine task workdir")
            workdir = (result.stdout or "").strip()

        command = (
            f"{REMOTE_VENV}/bin/python {REMOTE_RUNNER} "
            f"--instruction-path {REMOTE_INSTRUCTION} "
            f"--logs-dir {REMOTE_LOGS} "
            f"--model {shlex.quote(self.model_name)} "
            f"--max-turns {self.max_turns}"
        )
        await self.exec_as_agent(
            environment,
            command=f"{command} 2>&1 | stdbuf -oL tee {REMOTE_LOGS}/pagentv4.txt",
            cwd=workdir,
            env=self.build_agent_env(),
        )

    @override
    def populate_context_post_run(self, context: AgentContext) -> None:
        summary_path = self.logs_dir / "summary.json"
        if not summary_path.exists():
            return
        summary = json.loads(summary_path.read_text())
        context.n_input_tokens = int(summary.get("input_tokens", 0))
        context.n_output_tokens = int(summary.get("output_tokens", 0))
        context.n_cache_tokens = int(summary.get("cache_tokens", 0))
        context.metadata = {
            "pagentv4_stop_reason": summary.get("stop_reason", "unknown"),
            "pagentv4_max_turns": summary.get("max_turns", self.max_turns),
        }
