"""pagentv5 tools - register a function and run the complete tool loop.

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    uv run python -m examples.pagentv5.tools
"""

import asyncio
import os
import sys

from pagentv5 import Provider, Runner, tool


@tool()
def get_weather(city: str) -> str:
    """Get the current weather for a city.

    Args:
        city: City name.
    """
    return f"{city}: 24 C, clear"


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    provider = Provider("deepseek-v4-flash", provider_id="deepseek")
    runner = Runner(
        provider,
        tools=[get_weather],
        event_types={"text_delta", "tool_result"},
    )
    messages = [
        {
            "role": "user",
            "content": "查询北京天气，然后用一句中文回答。",
        }
    ]

    async for event in runner.run(messages):
        if event.type == "tool_result":
            print(f"\n[tool] {event.name}: {event.content}")
            continue
        sys.stdout.write(event.delta)
        sys.stdout.flush()
    print()


if __name__ == "__main__":
    asyncio.run(main())
