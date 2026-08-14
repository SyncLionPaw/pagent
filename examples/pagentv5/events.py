"""pagentv5 事件流 —— 观察一次 run 的完整生命周期。

Runner 对外产出的每个事件都带 category="runner" 和 run/turn/step 上下文。
一次 run 的事件序列形如：

    run_start
      turn_start
        step_start
          response_start
          text_start / text_delta ... / text_end
          （若模型发起工具调用：tool_call_start / _delta / _end）
          response_end
        step_end
        step_start (tool_execution)
          tool_result
        step_end
      turn_end
    run_end

这里全量订阅（event_types=None），把事件类型和关键字段打印出来。
文本增量原样拼接，其余事件打印一行摘要。

Usage:
    export DEEPSEEK_API_KEY="your-key-here"
    uv run python -m examples.pagentv5.events
"""

import asyncio
import os

from pagentv5 import Provider, Runner
from pagentv5.events import (
    ResponseEndEvent,
    RunEnd,
    TextDeltaEvent,
    ToolCallEndEvent,
    ToolResultEvent,
)


def describe(event) -> str | None:
    if isinstance(event, TextDeltaEvent):
        return None  # 文本增量单独拼接，不逐条打印
    if isinstance(event, ToolCallEndEvent):
        return f"  tool_call_end  {event.name}({event.arguments})"
    if isinstance(event, ToolResultEvent):
        return f"  tool_result    {event.name}: {event.content}"
    if isinstance(event, ResponseEndEvent):
        usage = event.usage
        return (
            f"  response_end   stop={event.stop_reason} "
            f"in={usage.input_tokens} out={usage.output_tokens}"
        )
    if isinstance(event, RunEnd):
        return f"run_end          stop={event.stop_reason} turns={event.turn_count}"
    return f"  {event.type}"


async def main() -> None:
    if not os.getenv("DEEPSEEK_API_KEY"):
        raise SystemExit("请先 export DEEPSEEK_API_KEY=<your-key>")

    provider = Provider("deepseek-v4-flash", provider_id="deepseek")
    runner = Runner(provider)

    messages = [
        {"role": "user", "content": "用两句话介绍一下事件溯源。"},
    ]

    text_parts: list[str] = []
    async for event in runner.run(messages):
        if isinstance(event, TextDeltaEvent):
            text_parts.append(event.delta)
        line = describe(event)
        if line is not None:
            print(line)

    print("\n--- 完整回答 ---")
    print("".join(text_parts))


if __name__ == "__main__":
    asyncio.run(main())
