"""Use SandboxWorker with an isolated Podman container.

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    uv run python -m examples.pagentv5.sdk.sandbox_worker
"""

import asyncio
import os

from pagentv5 import SandboxWorker


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    async with SandboxWorker(
        "deepseek-v4-flash",
        provider_id="deepseek",
        max_turns=32,
        yolo=True,
        emit_type="text",
        sandbox="container:podman:docker.io/library/debian:bookworm-slim",
    ) as agent:
        answer = await agent.ask("创建 hello.txt，然后告诉我文件内容。")
        print(answer)


if __name__ == "__main__":
    asyncio.run(main())
