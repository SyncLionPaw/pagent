"""Use BaseAgent for a stateful model session without filesystem tools.

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    uv run python -m examples.pagentv5.sdk.base_agent
"""

import asyncio
import os

from pagentv5 import BaseAgent


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    async with BaseAgent(
        "deepseek-v4-flash",
        provider_id="deepseek",
        max_turns=32,
        emit_type="event",
    ) as agent:
        async for event in agent.run("用一句话解释 Run、Turn、Step。"):
            print(event.type)


if __name__ == "__main__":
    asyncio.run(main())
