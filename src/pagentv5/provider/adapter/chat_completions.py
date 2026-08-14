from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass, field

from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from openai.types.completion_usage import CompletionUsage

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
    tool_call_id: str | None = None
    name: str | None = None
    argument_chunks: list[str] = field(default_factory=list)
    emitted_argument_length: int = 0
    started: bool = False
    ended: bool = False

    @property
    def arguments(self) -> str:
        return "".join(self.argument_chunks)


@dataclass
class CompletionsHandlerState:
    started: bool = False
    next_content_index: int = 0
    text: ContentState | None = None
    reasoning: ContentState | None = None
    tool_calls: dict[int, ToolCallState] = field(default_factory=dict)
    finish_reason: str | None = None
    usage: CompletionUsage | None = None

    def take_content_index(self) -> int:
        content_index = self.next_content_index
        self.next_content_index += 1
        return content_index


def convert_usage(usage: CompletionUsage | None) -> Usage:
    if usage is None:
        return Usage(input_tokens=0, output_tokens=0)

    completion_details = usage.completion_tokens_details
    prompt_details = usage.prompt_tokens_details
    return Usage(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        reasoning_tokens=(
            completion_details.reasoning_tokens
            if completion_details and completion_details.reasoning_tokens
            else 0
        ),
        cache_read_tokens=(
            prompt_details.cached_tokens
            if prompt_details and prompt_details.cached_tokens
            else 0
        ),
    )


def map_stop_reason(reason: str | None) -> str:
    if reason in {"tool_calls", "function_call"}:
        return "tool_use"
    if reason == "length":
        return "length"
    return "stop"


def handle_reasoning_delta(
    state: CompletionsHandlerState, delta: str
) -> list[ProviderMessage]:
    messages: list[ProviderMessage] = []
    if state.reasoning is None:
        state.reasoning = ContentState(state.take_content_index())
        messages.append(ReasoningStart(content_index=state.reasoning.content_index))
    state.reasoning.chunks.append(delta)
    messages.append(
        ReasoningDelta(content_index=state.reasoning.content_index, delta=delta)
    )
    return messages


def handle_text_delta(
    state: CompletionsHandlerState, delta: str
) -> list[ProviderMessage]:
    messages: list[ProviderMessage] = []
    if state.text is None:
        state.text = ContentState(state.take_content_index())
        messages.append(TextStart(content_index=state.text.content_index))
    state.text.chunks.append(delta)
    messages.append(TextDelta(content_index=state.text.content_index, delta=delta))
    return messages


def handle_tool_call_delta(
    state: CompletionsHandlerState, tool_call: ChoiceDeltaToolCall
) -> list[ProviderMessage]:
    call = state.tool_calls.get(tool_call.index)
    if call is None:
        call = ToolCallState(state.take_content_index())
        state.tool_calls[tool_call.index] = call

    if tool_call.id:
        call.tool_call_id = tool_call.id
    if tool_call.function and tool_call.function.name:
        call.name = tool_call.function.name
    if tool_call.function and tool_call.function.arguments:
        call.argument_chunks.append(tool_call.function.arguments)

    messages: list[ProviderMessage] = []
    if not call.started and call.tool_call_id is not None and call.name is not None:
        messages.append(
            ToolCallStart(
                content_index=call.content_index,
                tool_call_id=call.tool_call_id,
                name=call.name,
            )
        )
        call.started = True

    if not call.started:
        return messages

    arguments_delta = call.arguments[call.emitted_argument_length :]
    if arguments_delta:
        messages.append(
            ToolCallDelta(
                content_index=call.content_index,
                tool_call_id=call.tool_call_id or "",
                arguments_delta=arguments_delta,
            )
        )
        call.emitted_argument_length = len(call.arguments)
    return messages


def handle_chunk(
    chunk: ChatCompletionChunk, state: CompletionsHandlerState
) -> list[ProviderMessage]:
    if chunk.usage is not None:
        state.usage = chunk.usage

    messages: list[ProviderMessage] = []
    for choice in chunk.choices:
        if choice.index != 0:
            raise ValueError("multiple completion choices are not supported")
        if choice.finish_reason is not None:
            state.finish_reason = choice.finish_reason

        delta = choice.delta
        reasoning_delta = getattr(delta, "reasoning_content", None)
        if reasoning_delta:
            messages.extend(handle_reasoning_delta(state, reasoning_delta))
        if delta.content:
            messages.extend(handle_text_delta(state, delta.content))
        for tool_call in delta.tool_calls or []:
            messages.extend(handle_tool_call_delta(state, tool_call))
    return messages


def finish_open_blocks(state: CompletionsHandlerState) -> list[ProviderMessage]:
    messages: list[ProviderMessage] = []
    if state.text is not None and not state.text.ended:
        state.text.ended = True
        messages.append(
            TextEnd(content_index=state.text.content_index, text=state.text.content)
        )
    if state.reasoning is not None and not state.reasoning.ended:
        state.reasoning.ended = True
        messages.append(
            ReasoningEnd(
                content_index=state.reasoning.content_index,
                text=state.reasoning.content,
            )
        )
    for call in state.tool_calls.values():
        if call.ended:
            continue
        if call.tool_call_id is None or call.name is None:
            raise ValueError("incomplete tool call in completion stream")
        call.ended = True
        if not call.started:
            messages.append(
                ToolCallStart(
                    content_index=call.content_index,
                    tool_call_id=call.tool_call_id,
                    name=call.name,
                )
            )
        messages.append(
            ToolCallEnd(
                content_index=call.content_index,
                tool_call_id=call.tool_call_id,
                name=call.name,
                arguments=call.arguments,
            )
        )
    return messages


async def adapt_chat_completions(
    stream: AsyncIterable[ChatCompletionChunk],
) -> AsyncIterator[ProviderMessage]:
    state = CompletionsHandlerState()
    try:
        async for chunk in stream:
            if not state.started:
                yield ResponseStart(response_id=chunk.id)
                state.started = True
            for message in handle_chunk(chunk, state):
                yield message

        if not state.started:
            yield ResponseStart()
        for message in finish_open_blocks(state):
            yield message
        yield ResponseEnd(
            stop_reason=map_stop_reason(state.finish_reason),
            usage=convert_usage(state.usage),
        )
    except Exception as error:
        yield ResponseError(reason="error", message=str(error))
