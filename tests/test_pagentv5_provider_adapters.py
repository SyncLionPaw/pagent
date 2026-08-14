from collections.abc import AsyncIterator

import pytest
from openai.types.chat import ChatCompletionChunk
from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseOutputItemAddedEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
)
from openai.types.responses.response import Response
from openai.types.responses.response_function_tool_call import (
    ResponseFunctionToolCall,
)

from pagentv5.provider import ResponseEnd, TextEnd, ToolCallEnd
from pagentv5.provider.adapter import adapt_chat_completions, adapt_responses


async def stream_events(*events: object) -> AsyncIterator:
    for event in events:
        yield event


def chat_chunk(
    *,
    delta: dict,
    finish_reason: str | None = None,
    usage: dict | None = None,
) -> ChatCompletionChunk:
    return ChatCompletionChunk.model_validate(
        {
            "id": "chat_1",
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
            "created": 0,
            "model": "test-model",
            "object": "chat.completion.chunk",
            "usage": usage,
        }
    )


def response(
    *,
    output: list | None = None,
    usage: dict | None = None,
) -> Response:
    return Response.model_validate(
        {
            "id": "resp_1",
            "created_at": 0,
            "model": "test-model",
            "object": "response",
            "output": output or [],
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "usage": usage,
        }
    )


@pytest.mark.asyncio
async def test_chat_completions_adapter_converts_text_and_usage():
    stream = stream_events(
        chat_chunk(delta={"content": "hel"}),
        chat_chunk(
            delta={"content": "lo"},
            finish_reason="stop",
            usage={
                "prompt_tokens": 5,
                "completion_tokens": 2,
                "total_tokens": 7,
                "prompt_tokens_details": {"cached_tokens": 3},
                "completion_tokens_details": {"reasoning_tokens": 1},
            },
        ),
    )

    events = [event async for event in adapt_chat_completions(stream)]

    assert [event.type for event in events] == [
        "response_start",
        "text_start",
        "text_delta",
        "text_delta",
        "text_end",
        "response_end",
    ]
    assert isinstance(events[-2], TextEnd)
    assert events[-2].text == "hello"
    assert isinstance(events[-1], ResponseEnd)
    assert events[-1].usage.input_tokens == 5
    assert events[-1].usage.reasoning_tokens == 1
    assert events[-1].usage.cache_read_tokens == 3


@pytest.mark.asyncio
async def test_chat_completions_adapter_assembles_tool_call():
    stream = stream_events(
        chat_chunk(
            delta={
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "search",
                            "arguments": '{"query":',
                        },
                    }
                ]
            }
        ),
        chat_chunk(
            delta={
                "tool_calls": [
                    {
                        "index": 0,
                        "function": {"arguments": '"pagent"}'},
                    }
                ]
            },
            finish_reason="tool_calls",
        ),
    )

    events = [event async for event in adapt_chat_completions(stream)]
    tool_end = next(event for event in events if isinstance(event, ToolCallEnd))
    response_end = next(event for event in events if isinstance(event, ResponseEnd))

    assert tool_end.tool_call_id == "call_1"
    assert tool_end.name == "search"
    assert tool_end.arguments == '{"query":"pagent"}'
    assert response_end.stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_responses_adapter_converts_text_and_usage():
    created_response = response()
    completed_response = response(
        usage={
            "input_tokens": 8,
            "output_tokens": 3,
            "total_tokens": 11,
            "input_tokens_details": {"cached_tokens": 2},
            "output_tokens_details": {"reasoning_tokens": 1},
        }
    )
    stream = stream_events(
        ResponseCreatedEvent(
            response=created_response,
            sequence_number=0,
            type="response.created",
        ),
        ResponseTextDeltaEvent(
            content_index=0,
            delta="hello",
            item_id="msg_1",
            logprobs=[],
            output_index=0,
            sequence_number=1,
            type="response.output_text.delta",
        ),
        ResponseTextDoneEvent(
            content_index=0,
            item_id="msg_1",
            logprobs=[],
            output_index=0,
            sequence_number=2,
            text="hello",
            type="response.output_text.done",
        ),
        ResponseCompletedEvent(
            response=completed_response,
            sequence_number=3,
            type="response.completed",
        ),
    )

    events = [event async for event in adapt_responses(stream)]

    assert [event.type for event in events] == [
        "response_start",
        "text_start",
        "text_delta",
        "text_end",
        "response_end",
    ]
    assert isinstance(events[-1], ResponseEnd)
    assert events[-1].usage.input_tokens == 8
    assert events[-1].usage.reasoning_tokens == 1


@pytest.mark.asyncio
async def test_responses_adapter_assembles_tool_call():
    tool = ResponseFunctionToolCall(
        arguments="",
        call_id="call_1",
        id="item_1",
        name="search",
        status="in_progress",
        type="function_call",
    )
    completed_tool = tool.model_copy(
        update={"arguments": '{"query":"pagent"}', "status": "completed"}
    )
    stream = stream_events(
        ResponseCreatedEvent(
            response=response(),
            sequence_number=0,
            type="response.created",
        ),
        ResponseOutputItemAddedEvent(
            item=tool,
            output_index=0,
            sequence_number=1,
            type="response.output_item.added",
        ),
        ResponseFunctionCallArgumentsDeltaEvent(
            delta='{"query":"pagent"}',
            item_id="item_1",
            output_index=0,
            sequence_number=2,
            type="response.function_call_arguments.delta",
        ),
        ResponseFunctionCallArgumentsDoneEvent(
            arguments='{"query":"pagent"}',
            item_id="item_1",
            name="search",
            output_index=0,
            sequence_number=3,
            type="response.function_call_arguments.done",
        ),
        ResponseCompletedEvent(
            response=response(output=[completed_tool]),
            sequence_number=4,
            type="response.completed",
        ),
    )

    events = [event async for event in adapt_responses(stream)]
    tool_end = next(event for event in events if isinstance(event, ToolCallEnd))
    response_end = next(event for event in events if isinstance(event, ResponseEnd))

    assert tool_end.tool_call_id == "call_1"
    assert tool_end.name == "search"
    assert tool_end.arguments == '{"query":"pagent"}'
    assert response_end.stop_reason == "tool_use"
