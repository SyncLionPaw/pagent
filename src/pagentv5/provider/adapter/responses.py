from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass, field
from functools import singledispatch

from openai.types.responses import (
    ResponseCompletedEvent,
    ResponseCreatedEvent,
    ResponseErrorEvent,
    ResponseFailedEvent,
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionCallArgumentsDoneEvent,
    ResponseIncompleteEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseReasoningSummaryTextDoneEvent,
    ResponseReasoningTextDeltaEvent,
    ResponseReasoningTextDoneEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
    ResponseTextDoneEvent,
)
from openai.types.responses.response import Response
from openai.types.responses.response_function_tool_call import (
    ResponseFunctionToolCall,
)

from ..messages import (
    ProviderMessage,
    ReasoningDelta,
    ReasoningEnd,
    ReasoningStart,
    ResponseEnd,
    ResponseError,
    ResponseStart,
    TextDelta,
    TextEnd,
    TextStart,
    ToolCallDelta,
    ToolCallEnd,
    ToolCallStart,
    Usage,
)


@dataclass
class ContentState:
    content_index: int
    chunks: list[str] = field(default_factory=list)
    ended: bool = False

    @property
    def content(self) -> str:
        return "".join(self.chunks)


@dataclass
class ToolCallState:
    content_index: int
    tool_call_id: str
    name: str
    argument_chunks: list[str] = field(default_factory=list)
    ended: bool = False

    @property
    def arguments(self) -> str:
        return "".join(self.argument_chunks)


def convert_usage(response: Response) -> Usage:
    usage = response.usage
    if usage is None:
        return Usage(input_tokens=0, output_tokens=0)
    return Usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
        cache_read_tokens=usage.input_tokens_details.cached_tokens,
    )


def response_uses_tools(response: Response) -> bool:
    return any(item.type == "function_call" for item in response.output)


@dataclass
class ResponsesHandlerState:
    started: bool = False
    terminal: bool = False
    next_content_index: int = 0
    text_blocks: dict[tuple[str, int], ContentState] = field(default_factory=dict)
    reasoning_blocks: dict[tuple[str, str, int], ContentState] = field(
        default_factory=dict
    )
    tool_calls: dict[str, ToolCallState] = field(default_factory=dict)

    def take_content_index(self) -> int:
        content_index = self.next_content_index
        self.next_content_index += 1
        return content_index


def finish_open_blocks(state: ResponsesHandlerState) -> list[ProviderMessage]:
    messages: list[ProviderMessage] = []
    for block in state.text_blocks.values():
        if block.ended:
            continue
        block.ended = True
        messages.append(TextEnd(content_index=block.content_index, text=block.content))
    for block in state.reasoning_blocks.values():
        if block.ended:
            continue
        block.ended = True
        messages.append(
            ReasoningEnd(content_index=block.content_index, text=block.content)
        )
    for tool_call in state.tool_calls.values():
        if tool_call.ended:
            continue
        tool_call.ended = True
        messages.append(
            ToolCallEnd(
                content_index=tool_call.content_index,
                tool_call_id=tool_call.tool_call_id,
                name=tool_call.name,
                arguments=tool_call.arguments,
            )
        )
    return messages


def handle_reasoning_delta(
    state: ResponsesHandlerState,
    *,
    reasoning_type: str,
    item_id: str,
    sub_index: int,
    delta: str,
) -> list[ProviderMessage]:
    key = (reasoning_type, item_id, sub_index)
    block = state.reasoning_blocks.get(key)
    messages: list[ProviderMessage] = []
    if block is None:
        block = ContentState(state.take_content_index())
        state.reasoning_blocks[key] = block
        messages.append(ReasoningStart(content_index=block.content_index))
    block.chunks.append(delta)
    messages.append(ReasoningDelta(content_index=block.content_index, delta=delta))
    return messages


def handle_reasoning_end(
    state: ResponsesHandlerState,
    *,
    reasoning_type: str,
    item_id: str,
    sub_index: int,
    text: str,
) -> list[ProviderMessage]:
    key = (reasoning_type, item_id, sub_index)
    block = state.reasoning_blocks.get(key)
    messages: list[ProviderMessage] = []
    if block is None:
        block = ContentState(state.take_content_index())
        state.reasoning_blocks[key] = block
        messages.append(ReasoningStart(content_index=block.content_index))
    block.chunks = [text]
    block.ended = True
    messages.append(ReasoningEnd(content_index=block.content_index, text=text))
    return messages


@singledispatch
def handle_response_event(
    event: object,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    return []


@handle_response_event.register
def handle_response_created(
    event: ResponseCreatedEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    if state.started:
        return []
    state.started = True
    return [ResponseStart(response_id=event.response.id)]


@handle_response_event.register
def handle_text_delta(
    event: ResponseTextDeltaEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    key = (event.item_id, event.content_index)
    block = state.text_blocks.get(key)
    messages: list[ProviderMessage] = []
    if block is None:
        block = ContentState(state.take_content_index())
        state.text_blocks[key] = block
        messages.append(TextStart(content_index=block.content_index))
    block.chunks.append(event.delta)
    messages.append(TextDelta(content_index=block.content_index, delta=event.delta))
    return messages


@handle_response_event.register
def handle_text_done(
    event: ResponseTextDoneEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    key = (event.item_id, event.content_index)
    block = state.text_blocks.get(key)
    messages: list[ProviderMessage] = []
    if block is None:
        block = ContentState(state.take_content_index())
        state.text_blocks[key] = block
        messages.append(TextStart(content_index=block.content_index))
    block.chunks = [event.text]
    block.ended = True
    messages.append(TextEnd(content_index=block.content_index, text=event.text))
    return messages


@handle_response_event.register
def handle_reasoning_text_delta(
    event: ResponseReasoningTextDeltaEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    return handle_reasoning_delta(
        state,
        reasoning_type="reasoning_text",
        item_id=event.item_id,
        sub_index=event.content_index,
        delta=event.delta,
    )


@handle_response_event.register
def handle_reasoning_summary_delta(
    event: ResponseReasoningSummaryTextDeltaEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    return handle_reasoning_delta(
        state,
        reasoning_type="reasoning_summary",
        item_id=event.item_id,
        sub_index=event.summary_index,
        delta=event.delta,
    )


@handle_response_event.register
def handle_reasoning_text_done(
    event: ResponseReasoningTextDoneEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    return handle_reasoning_end(
        state,
        reasoning_type="reasoning_text",
        item_id=event.item_id,
        sub_index=event.content_index,
        text=event.text,
    )


@handle_response_event.register
def handle_reasoning_summary_done(
    event: ResponseReasoningSummaryTextDoneEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    return handle_reasoning_end(
        state,
        reasoning_type="reasoning_summary",
        item_id=event.item_id,
        sub_index=event.summary_index,
        text=event.text,
    )


@handle_response_event.register
def handle_output_item_added(
    event: ResponseOutputItemAddedEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    if not isinstance(event.item, ResponseFunctionToolCall):
        return []

    item_id = event.item.id or event.item.call_id
    tool_call = ToolCallState(
        content_index=state.take_content_index(),
        tool_call_id=event.item.call_id,
        name=event.item.name,
    )
    state.tool_calls[item_id] = tool_call
    messages: list[ProviderMessage] = [
        ToolCallStart(
            content_index=tool_call.content_index,
            tool_call_id=tool_call.tool_call_id,
            name=tool_call.name,
        )
    ]
    if event.item.arguments:
        tool_call.argument_chunks.append(event.item.arguments)
        messages.append(
            ToolCallDelta(
                content_index=tool_call.content_index,
                tool_call_id=tool_call.tool_call_id,
                arguments_delta=event.item.arguments,
            )
        )
    return messages


@handle_response_event.register
def handle_function_arguments_delta(
    event: ResponseFunctionCallArgumentsDeltaEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    tool_call = state.tool_calls.get(event.item_id)
    if tool_call is None:
        raise ValueError(f"tool call arguments arrived before item {event.item_id!r}")
    tool_call.argument_chunks.append(event.delta)
    return [
        ToolCallDelta(
            content_index=tool_call.content_index,
            tool_call_id=tool_call.tool_call_id,
            arguments_delta=event.delta,
        )
    ]


@handle_response_event.register
def handle_function_arguments_done(
    event: ResponseFunctionCallArgumentsDoneEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    tool_call = state.tool_calls.get(event.item_id)
    if tool_call is None:
        raise ValueError(f"tool call completion arrived before item {event.item_id!r}")
    tool_call.argument_chunks = [event.arguments]
    tool_call.ended = True
    return [
        ToolCallEnd(
            content_index=tool_call.content_index,
            tool_call_id=tool_call.tool_call_id,
            name=event.name,
            arguments=event.arguments,
        )
    ]


@handle_response_event.register
def handle_output_item_done(
    event: ResponseOutputItemDoneEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    if not isinstance(event.item, ResponseFunctionToolCall):
        return []
    item_id = event.item.id or event.item.call_id
    tool_call = state.tool_calls.get(item_id)
    if tool_call is None or tool_call.ended:
        return []
    tool_call.argument_chunks = [event.item.arguments]
    tool_call.ended = True
    return [
        ToolCallEnd(
            content_index=tool_call.content_index,
            tool_call_id=tool_call.tool_call_id,
            name=tool_call.name,
            arguments=event.item.arguments,
        )
    ]


@handle_response_event.register
def handle_response_completed(
    event: ResponseCompletedEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    messages = finish_open_blocks(state)
    messages.append(
        ResponseEnd(
            stop_reason=("tool_use" if response_uses_tools(event.response) else "stop"),
            usage=convert_usage(event.response),
        )
    )
    state.terminal = True
    return messages


@handle_response_event.register
def handle_response_incomplete(
    event: ResponseIncompleteEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    reason = (
        event.response.incomplete_details.reason
        if event.response.incomplete_details
        else None
    )
    state.terminal = True
    if reason == "max_output_tokens":
        messages = finish_open_blocks(state)
        messages.append(
            ResponseEnd(
                stop_reason="length",
                usage=convert_usage(event.response),
            )
        )
        return messages
    return [
        ResponseError(
            reason="error",
            message=f"incomplete response: {reason or 'unknown'}",
            code=reason,
        )
    ]


@handle_response_event.register
def handle_response_failed(
    event: ResponseFailedEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    state.terminal = True
    error = event.response.error
    return [
        ResponseError(
            reason="error",
            message=error.message if error else "response failed",
            code=error.code if error else None,
        )
    ]


@handle_response_event.register
def handle_response_error(
    event: ResponseErrorEvent,
    state: ResponsesHandlerState,
) -> list[ProviderMessage]:
    state.terminal = True
    return [
        ResponseError(
            reason="error",
            message=event.message,
            code=event.code,
        )
    ]


async def adapt_responses(
    stream: AsyncIterable[ResponseStreamEvent],
) -> AsyncIterator[ProviderMessage]:
    state = ResponsesHandlerState()
    try:
        async for event in stream:
            if not state.started and not isinstance(event, ResponseCreatedEvent):
                yield ResponseStart()
                state.started = True
            for message in handle_response_event(event, state):
                yield message
            if state.terminal:
                return

        if not state.started:
            yield ResponseStart()
        yield ResponseError(
            reason="error",
            message="response stream ended without a terminal event",
        )
    except Exception as error:
        yield ResponseError(reason="error", message=str(error))
