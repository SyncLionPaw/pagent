"""Use SandboxWorker on a remote machine over SSH.

Authentication uses ssh-agent and the normal AsyncSSH key discovery.

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    export PAGENT_SSH_HOST="server.example.com"
    export PAGENT_SSH_USER="agent"
    export PAGENT_SSH_PORT="22"                    # optional
    export PAGENT_SSH_WORKDIR="~/pagent-workspace" # optional
    uv run python -m examples.pagentv5.sdk.sandbox_worker_ssh
"""

import asyncio
import os
from pathlib import Path

from pagentv5 import SandboxWorker


def ssh_connection() -> dict[str, str]:
    host = os.getenv("PAGENT_SSH_HOST", "").strip()
    user = os.getenv("PAGENT_SSH_USER", "").strip()
    if not host or not user:
        raise SystemExit("请设置 PAGENT_SSH_HOST 和 PAGENT_SSH_USER")

    known_hosts = os.getenv(
        "PAGENT_SSH_KNOWN_HOSTS",
        str(Path("~/.ssh/known_hosts").expanduser()),
    )
    return {
        "host": host,
        "user": user,
        "port": os.getenv("PAGENT_SSH_PORT", "22"),
        "workdir": os.getenv("PAGENT_SSH_WORKDIR", "~/pagent-workspace"),
        "known_hosts": known_hosts,
    }


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    async with SandboxWorker(
        "deepseek-v4-flash",
        provider_id="deepseek",
        sandbox="ssh",
        sandbox_connection=ssh_connection(),
        max_turns=32,
        yolo=True,
        emit_type="text",
    ) as agent:
        answer = await agent.ask(
            "运行 uname -a 和 pwd，概括这台远程机器及当前工作目录。"
        )
        print(answer)


if __name__ == "__main__":
    asyncio.run(main())
