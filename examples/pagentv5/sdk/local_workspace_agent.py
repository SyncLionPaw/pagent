"""Use LocalWorkspaceAgent to work directly in a local directory.

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    export PAGENT_WORKSPACE_PATH="/path/to/directory"  # optional, defaults to cwd
    uv run python -m examples.pagentv5.sdk.local_workspace_agent
"""

import asyncio
import os
from pathlib import Path

from pagentv5 import LocalWorkspaceAgent, SessionConfig


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    workspace_path = Path(os.getenv("PAGENT_WORKSPACE_PATH", ".")).resolve()
    async with LocalWorkspaceAgent(
        "deepseek-v4-flash",
        provider_id="deepseek",
        workspace_path=workspace_path,
        session=SessionConfig(
            storage="jsonl",
            session_id="local-workspace-agent",
        ),
        max_turns=32,
        yolo=True,
        emit_type="text",
    ) as agent:
        async for text in agent.run("列出当前工作目录中的文件。"):
            print(text, end="", flush=True)
        print()


if __name__ == "__main__":
    asyncio.run(main())
