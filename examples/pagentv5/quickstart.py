"""pagentv5 quickstart —— 配一个 Provider，流式打印回答。

pagentv5 的 Runner 消费 Provider 产出的模型无关消息流，翻译成带
run/turn/step 上下文的事件。这里只订阅 text_delta，边到边打印。

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    uv run python -m examples.pagentv5.quickstart
"""

import asyncio
import os
import sys

from pagentv5 import Provider, Runner


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    provider = Provider("deepseek-v4-flash", provider_id="deepseek")
    runner = Runner(provider, event_types={"text_delta"})

    messages = [
        {"role": "system", "content": "你是一个简洁的助手，回答不超过两句。"},
        {"role": "user", "content": "用一句话解释什么是尾递归。"},
    ]

    async for event in runner.run(messages):
        sys.stdout.write(event.delta)
        sys.stdout.flush()
    print()


if __name__ == "__main__":
    asyncio.run(main())
