"""Use LocalCodeAgent to work directly in a local project.

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    export PAGENT_PROJECT_PATH="/path/to/project"  # optional, defaults to cwd
    uv run python -m examples.pagentv5.sdk.local_code_agent
"""

import asyncio
import os
from pathlib import Path

from pagentv5 import LocalCodeAgent, SessionConfig


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    project_path = Path(os.getenv("PAGENT_PROJECT_PATH", ".")).resolve()
    async with LocalCodeAgent(
        "deepseek-v4-flash",
        provider_id="deepseek",
        project_path=project_path,
        session=SessionConfig(storage="jsonl", session_id="local-code-agent"),
        max_turns=32,
        yolo=True,
        emit_type="text",
    ) as agent:
        async for text in agent.run("列出当前项目根目录中的文件。"):
            print(text, end="", flush=True)
        print()


if __name__ == "__main__":
    asyncio.run(main())
