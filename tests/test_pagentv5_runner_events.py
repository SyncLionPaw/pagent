import pytest
from pydantic import TypeAdapter, ValidationError

from pagentv5.events import (
    ResponseEndEvent,
    RunEnd,
    RunnerEvent,
    RunStart,
    StepEnd,
    StepStart,
    TextDeltaEvent,
    TurnStart,
)
from pagentv5.provider import ResponseEnd, ResponseStart, TextDelta, Usage
from pagentv5.runtime import TranslationContext, translate_provider_stream


async def provider_messages(*messages):
    for message in messages:
        yield message


def test_runner_event_uses_type_discriminator():
    event = TypeAdapter(RunnerEvent).validate_python(
        {
            "type": "step_start",
            "run_id": "run_1",
            "turn_index": 2,
            "step_index": 1,
            "step_type": "tool_execution",
        }
    )

    assert event == StepStart(
        run_id="run_1",
        turn_index=2,
        step_index=1,
        step_type="tool_execution",
    )
    assert event.category == "runner"


def test_run_start_records_trigger_source():
    event = RunStart(
        run_id="run_1",
        trigger_type="goal",
        trigger_id="goal_42:completed",
    )

    assert event.trigger_type == "goal"
    assert event.trigger_id == "goal_42:completed"


def test_turn_start_can_mark_synthesis_turn():
    event = TurnStart(run_id="run_1", turn_index=4, synthesis=True)

    assert event.synthesis is True


def test_step_end_records_status():
    event = StepEnd(
        run_id="run_1",
        turn_index=0,
        step_index=0,
        step_type="model_generation",
        status="completed",
    )

    assert event.status == "completed"


def test_run_end_records_turn_count():
    event = RunEnd(run_id="run_1", stop_reason="completed", turn_count=3)

    assert event.turn_count == 3


def test_runner_events_reject_invalid_indexes():
    with pytest.raises(ValidationError):
        StepStart(
            run_id="run_1",
            turn_index=-1,
            step_index=0,
            step_type="model_generation",
        )


@pytest.mark.asyncio
async def test_runner_translates_provider_messages_to_contextual_events():
    context = TranslationContext(run_id="run_1", turn_index=2, step_index=0)
    messages = provider_messages(
        ResponseStart(response_id="response_1"),
        TextDelta(content_index=0, delta="hello"),
        ResponseEnd(
            stop_reason="stop",
            usage=Usage(input_tokens=3, output_tokens=1),
        ),
    )

    events = [
        event async for event in translate_provider_stream(messages, context=context)
    ]

    assert [event.type for event in events] == [
        "response_start",
        "text_delta",
        "response_end",
    ]
    assert events[1] == TextDeltaEvent(
        run_id="run_1",
        turn_index=2,
        step_index=0,
        content_index=0,
        delta="hello",
    )
    assert events[2] == ResponseEndEvent(
        run_id="run_1",
        turn_index=2,
        step_index=0,
        stop_reason="stop",
        usage=Usage(input_tokens=3, output_tokens=1),
    )


@pytest.mark.asyncio
async def test_runner_filters_emitted_event_types():
    context = TranslationContext(run_id="run_1", turn_index=0, step_index=0)
    messages = provider_messages(
        ResponseStart(response_id="response_1"),
        TextDelta(content_index=0, delta="hello"),
        ResponseEnd(
            stop_reason="stop",
            usage=Usage(input_tokens=3, output_tokens=1),
        ),
    )

    events = [
        event
        async for event in translate_provider_stream(
            messages,
            context=context,
            event_types={"text_delta"},
        )
    ]

    assert events == [
        TextDeltaEvent(
            run_id="run_1",
            turn_index=0,
            step_index=0,
            content_index=0,
            delta="hello",
        )
    ]
