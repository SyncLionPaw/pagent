"""Persist a BaseAgent conversation as JSONL in the current directory.

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    uv run python -m examples.pagentv5.sdk.base_agent_persistent

Run the command again and ask about an earlier message to verify persistence.
The conversation is stored at ./sessions/base-agent.jsonl.
"""

import asyncio
import os
from pathlib import Path

from pagentv5 import BaseAgent, SessionConfig


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    session_path = Path.cwd() / "sessions" / "base-agent.jsonl"
    async with BaseAgent(
        "deepseek-v4-flash",
        provider_id="deepseek",
        session=SessionConfig(
            storage="jsonl",
            session_id="base-agent",
            root="sessions",
        ),
        session_base_path=Path.cwd(),
        emit_type="text",
    ) as agent:
        print(f"Session: {session_path}")
        question = input("You: ").strip()
        if not question:
            return
        print("Agent: ", end="", flush=True)
        async for text in agent.run(question):
            print(text, end="", flush=True)
        print()


if __name__ == "__main__":
    asyncio.run(main())
