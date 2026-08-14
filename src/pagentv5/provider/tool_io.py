from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .messages import ToolCallEnd

if TYPE_CHECKING:
    from .provider import ProviderInput


@dataclass(frozen=True, slots=True)
class ToolResultInput:
    tool_call_id: str
    content: str


def tools_for_api(
    tools: list[dict[str, Any]] | None,
    api_protocol: str,
) -> list[dict[str, Any]] | None:
    if tools is None:
        return None
    if api_protocol == "openai-completions":
        return [chat_completions_tool(tool) for tool in tools]
    if api_protocol == "openai-responses":
        return [responses_tool(tool) for tool in tools]
    raise ValueError(f"unsupported api_protocol {api_protocol!r}")


def chat_completions_tool(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool.get("function")
    if isinstance(function, dict):
        return tool
    return {
        "type": "function",
        "function": {
            key: value
            for key, value in tool.items()
            if key in {"name", "description", "parameters", "strict"}
        },
    }


def responses_tool(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool.get("function")
    if not isinstance(function, dict):
        return tool
    return {
        "type": "function",
        **{
            key: value
            for key, value in function.items()
            if key in {"name", "description", "parameters", "strict"}
        },
    }


def append_tool_round(
    input: ProviderInput,
    *,
    api_protocol: str,
    assistant_text: str,
    tool_calls: Sequence[ToolCallEnd],
    tool_results: Sequence[ToolResultInput],
) -> list[dict[str, Any]]:
    if len(tool_calls) != len(tool_results):
        raise ValueError("each tool call must have one tool result")

    if api_protocol == "openai-completions":
        return append_chat_completions_tool_round(
            input,
            assistant_text=assistant_text,
            tool_calls=tool_calls,
            tool_results=tool_results,
        )
    if api_protocol == "openai-responses":
        return append_responses_tool_round(
            input,
            assistant_text=assistant_text,
            tool_calls=tool_calls,
            tool_results=tool_results,
        )
    raise ValueError(f"unsupported api_protocol {api_protocol!r}")


def append_assistant_response(
    input: ProviderInput,
    *,
    text: str,
) -> list[dict[str, Any]]:
    if isinstance(input, str):
        items: list[dict[str, Any]] = [{"role": "user", "content": input}]
    else:
        items = list(input)
    if text:
        items.append({"role": "assistant", "content": text})
    return items


def append_chat_completions_tool_round(
    input: ProviderInput,
    *,
    assistant_text: str,
    tool_calls: Sequence[ToolCallEnd],
    tool_results: Sequence[ToolResultInput],
) -> list[dict[str, Any]]:
    if isinstance(input, str):
        raise TypeError("chat_completions input must be a list of messages")

    messages = list(input)
    messages.append(
        {
            "role": "assistant",
            "content": assistant_text or None,
            "tool_calls": [
                {
                    "id": call.tool_call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments,
                    },
                }
                for call in tool_calls
            ],
        }
    )
    messages.extend(
        {
            "role": "tool",
            "tool_call_id": result.tool_call_id,
            "content": result.content,
        }
        for result in tool_results
    )
    return messages


def append_responses_tool_round(
    input: ProviderInput,
    *,
    assistant_text: str,
    tool_calls: Sequence[ToolCallEnd],
    tool_results: Sequence[ToolResultInput],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]]
    if isinstance(input, str):
        items = [{"role": "user", "content": input}]
    else:
        items = list(input)

    if assistant_text:
        items.append({"role": "assistant", "content": assistant_text})
    items.extend(
        {
            "type": "function_call",
            "call_id": call.tool_call_id,
            "name": call.name,
            "arguments": call.arguments,
        }
        for call in tool_calls
    )
    items.extend(
        {
            "type": "function_call_output",
            "call_id": result.tool_call_id,
            "output": result.content,
        }
        for result in tool_results
    )
    return items
