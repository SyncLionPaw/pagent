"""把 pagentv4 的 Messages 规整成前端 HistoryReplay 需要的扁平数组。

形状与 src/app/wire.py 的 history_message_items 一致（前端 render.ts 按 kind 分派）：

- text/thinking：{"kind", "role", "text"}
- tool_call：{"kind": "tool_call", "tool_call_id", "name", "arguments"}
- tool_result：{"kind": "tool_result", "tool_call_id", "content"}

system 消息不回放（前端不展示系统提示）。
"""

from __future__ import annotations

from pagentv4.core.message import (
    Messages,
    TextChunk,
    ThinkingChunk,
    ToolCall,
    ToolResult,
)


def history_message_items(messages: Messages) -> list[dict]:
    out: list[dict] = []
    for message in messages.data:
        content = message.content
        if isinstance(content, TextChunk):
            if message.role == "system":
                continue
            out.append({"kind": "text", "role": message.role, "text": content.text})
        elif isinstance(content, ThinkingChunk):
            out.append({"kind": "thinking", "role": message.role, "text": content.text})
        elif isinstance(content, ToolCall):
            out.append(
                {
                    "kind": "tool_call",
                    "tool_call_id": content.id,
                    "name": content.name,
                    "arguments": content.arguments,
                }
            )
        elif isinstance(content, ToolResult):
            out.append(
                {
                    "kind": "tool_result",
                    "tool_call_id": content.tool_call_id,
                    "content": content.text,
                }
            )
    return out
