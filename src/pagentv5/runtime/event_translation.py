from collections.abc import AsyncIterable, AsyncIterator, Collection
from dataclasses import dataclass
from functools import singledispatch

from ..events import runner as runner_events
from ..provider import messages as provider_messages


@dataclass(frozen=True)
class TranslationContext:
    run_id: str
    turn_index: int
    step_index: int

    def fields(self) -> dict[str, str | int]:
        return {
            "run_id": self.run_id,
            "turn_index": self.turn_index,
            "step_index": self.step_index,
        }


@singledispatch
def translate_provider_message(
    message: object,
    context: TranslationContext,
) -> runner_events.RunnerEvent:
    raise TypeError(
        f"unsupported provider message in run {context.run_id!r}: "
        f"{type(message).__name__}"
    )


@translate_provider_message.register
def translate_response_start(
    message: provider_messages.ResponseStart,
    context: TranslationContext,
) -> runner_events.ResponseStartEvent:
    return runner_events.ResponseStartEvent(
        **context.fields(),
        response_id=message.response_id,
    )


@translate_provider_message.register
def translate_text_start(
    message: provider_messages.TextStart,
    context: TranslationContext,
) -> runner_events.TextStartEvent:
    return runner_events.TextStartEvent(
        **context.fields(),
        content_index=message.content_index,
    )


@translate_provider_message.register
def translate_text_delta(
    message: provider_messages.TextDelta,
    context: TranslationContext,
) -> runner_events.TextDeltaEvent:
    return runner_events.TextDeltaEvent(
        **context.fields(),
        content_index=message.content_index,
        delta=message.delta,
    )


@translate_provider_message.register
def translate_text_end(
    message: provider_messages.TextEnd,
    context: TranslationContext,
) -> runner_events.TextEndEvent:
    return runner_events.TextEndEvent(
        **context.fields(),
        content_index=message.content_index,
        text=message.text,
    )


@translate_provider_message.register
def translate_reasoning_start(
    message: provider_messages.ReasoningStart,
    context: TranslationContext,
) -> runner_events.ReasoningStartEvent:
    return runner_events.ReasoningStartEvent(
        **context.fields(),
        content_index=message.content_index,
    )


@translate_provider_message.register
def translate_reasoning_delta(
    message: provider_messages.ReasoningDelta,
    context: TranslationContext,
) -> runner_events.ReasoningDeltaEvent:
    return runner_events.ReasoningDeltaEvent(
        **context.fields(),
        content_index=message.content_index,
        delta=message.delta,
    )


@translate_provider_message.register
def translate_reasoning_end(
    message: provider_messages.ReasoningEnd,
    context: TranslationContext,
) -> runner_events.ReasoningEndEvent:
    return runner_events.ReasoningEndEvent(
        **context.fields(),
        content_index=message.content_index,
        text=message.text,
    )


@translate_provider_message.register
def translate_tool_call_start(
    message: provider_messages.ToolCallStart,
    context: TranslationContext,
) -> runner_events.ToolCallStartEvent:
    return runner_events.ToolCallStartEvent(
        **context.fields(),
        content_index=message.content_index,
        tool_call_id=message.tool_call_id,
        name=message.name,
    )


@translate_provider_message.register
def translate_tool_call_delta(
    message: provider_messages.ToolCallDelta,
    context: TranslationContext,
) -> runner_events.ToolCallDeltaEvent:
    return runner_events.ToolCallDeltaEvent(
        **context.fields(),
        content_index=message.content_index,
        tool_call_id=message.tool_call_id,
        arguments_delta=message.arguments_delta,
    )


@translate_provider_message.register
def translate_tool_call_end(
    message: provider_messages.ToolCallEnd,
    context: TranslationContext,
) -> runner_events.ToolCallEndEvent:
    return runner_events.ToolCallEndEvent(
        **context.fields(),
        content_index=message.content_index,
        tool_call_id=message.tool_call_id,
        name=message.name,
        arguments=message.arguments,
    )


@translate_provider_message.register
def translate_response_end(
    message: provider_messages.ResponseEnd,
    context: TranslationContext,
) -> runner_events.ResponseEndEvent:
    return runner_events.ResponseEndEvent(
        **context.fields(),
        stop_reason=message.stop_reason,
        usage=message.usage,
    )


@translate_provider_message.register
def translate_response_error(
    message: provider_messages.ResponseError,
    context: TranslationContext,
) -> runner_events.ResponseErrorEvent:
    return runner_events.ResponseErrorEvent(
        **context.fields(),
        reason=message.reason,
        message=message.message,
        code=message.code,
    )


def event_is_selected(
    event: runner_events.RunnerEvent,
    event_types: Collection[str] | None,
) -> bool:
    if event_types is None:
        return True
    return event.type in event_types


async def translate_provider_stream(
    messages: AsyncIterable[provider_messages.ProviderMessage],
    *,
    context: TranslationContext,
    event_types: Collection[str] | None = None,
) -> AsyncIterator[runner_events.RunnerEvent]:
    async for message in messages:
        event = translate_provider_message(message, context)
        if event_is_selected(event, event_types):
            yield event
