import pytest

from pagentv5 import tool
from pagentv5.events import ResponseErrorEvent, RunEnd
from pagentv5.provider import (
    ProviderMessage,
    ResponseEnd,
    ResponseError,
    ResponseStart,
    TextDelta,
    TextEnd,
    TextStart,
    Usage,
)
from pagentv5.runtime import Runner


class FakeProvider:
    def __init__(self, messages: list[ProviderMessage]) -> None:
        self.messages = messages

    async def complete(self, input, tools=None, **request_kwargs):
        del input, tools, request_kwargs
        for message in self.messages:
            yield message


class FailingProvider:
    async def complete(self, input, tools=None, **request_kwargs):
        del input, tools, request_kwargs
        yield ResponseStart(response_id="response_1")
        raise ConnectionError("provider unavailable")


def completed_usage() -> Usage:
    return Usage(input_tokens=4, output_tokens=2)


@pytest.mark.asyncio
async def test_runner_emits_complete_run_lifecycle():
    runner = Runner(
        FakeProvider(
            [
                ResponseStart(response_id="response_1"),
                TextStart(content_index=0),
                TextDelta(content_index=0, delta="hello"),
                TextEnd(content_index=0, text="hello"),
                ResponseEnd(stop_reason="stop", usage=completed_usage()),
            ]
        )
    )

    events = [event async for event in runner.run("hello", run_id="run_1")]

    assert [event.type for event in events] == [
        "run_start",
        "turn_start",
        "step_start",
        "response_start",
        "text_start",
        "text_delta",
        "text_end",
        "response_end",
        "step_end",
        "turn_end",
        "run_end",
    ]
    assert all(event.run_id == "run_1" for event in events)
    assert isinstance(events[-1], RunEnd)
    assert events[-1].stop_reason == "completed"
    assert events[-1].turn_count == 1
    assert runner.run_in_progress is False


@pytest.mark.asyncio
async def test_runner_filters_all_emitted_event_types():
    runner = Runner(
        FakeProvider(
            [
                ResponseStart(response_id="response_1"),
                TextDelta(content_index=0, delta="hello"),
                ResponseEnd(stop_reason="stop", usage=completed_usage()),
            ]
        ),
        event_types={"text_delta", "run_end"},
    )

    events = [event async for event in runner.run("hello", run_id="run_1")]

    assert [event.type for event in events] == ["text_delta", "run_end"]


@pytest.mark.asyncio
async def test_runner_marks_response_without_content_as_empty():
    runner = Runner(
        FakeProvider(
            [
                ResponseStart(response_id="response_1"),
                ResponseEnd(stop_reason="stop", usage=completed_usage()),
            ]
        )
    )

    events = [event async for event in runner.run("hello", run_id="run_1")]

    run_end = next(event for event in events if isinstance(event, RunEnd))
    assert run_end.stop_reason == "empty_response"


@pytest.mark.asyncio
async def test_runner_uses_provider_error_as_run_stop_reason():
    runner = Runner(
        FakeProvider(
            [
                ResponseStart(response_id="response_1"),
                ResponseError(reason="cancelled", message="cancelled"),
            ]
        )
    )

    events = [event async for event in runner.run("hello", run_id="run_1")]

    assert isinstance(events[-1], RunEnd)
    assert events[-1].stop_reason == "cancelled"
    assert events[-2].stop_reason == "cancelled"
    assert events[-3].status == "cancelled"


@pytest.mark.asyncio
async def test_runner_converts_provider_exception_to_error_events():
    runner = Runner(FailingProvider())

    events = [event async for event in runner.run("hello", run_id="run_1")]

    error = next(event for event in events if isinstance(event, ResponseErrorEvent))
    assert error.message == "provider unavailable"
    assert error.code == "ConnectionError"
    assert isinstance(events[-1], RunEnd)
    assert events[-1].stop_reason == "error"


@pytest.mark.asyncio
async def test_runner_rejects_concurrent_runs():
    runner = Runner(
        FakeProvider(
            [
                ResponseStart(response_id="response_1"),
                ResponseEnd(stop_reason="stop", usage=completed_usage()),
            ]
        )
    )
    first_run = runner.run("first", run_id="run_1")
    await anext(first_run)

    second_run = runner.run("second", run_id="run_2")
    with pytest.raises(RuntimeError, match="already has a run"):
        await anext(second_run)

    await first_run.aclose()
    assert runner.run_in_progress is False


@pytest.mark.asyncio
async def test_runner_can_change_tools_only_between_runs():
    @tool()
    def echo(text: str) -> str:
        return text

    runner = Runner(
        FakeProvider(
            [
                ResponseStart(response_id="response_1"),
                ResponseEnd(stop_reason="stop", usage=completed_usage()),
            ]
        )
    )
    runner.set_tools([echo])
    assert runner.tools == [echo]
    assert runner.tool_map == {"echo": echo}
    assert runner.tool_schemas == [echo.to_dict()]

    run = runner.run("hello")
    await anext(run)
    with pytest.raises(RuntimeError, match="cannot change tools"):
        runner.set_tools([])
    await run.aclose()
