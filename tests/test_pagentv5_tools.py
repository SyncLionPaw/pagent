import pytest

from pagentv5 import Runner, tool
from pagentv5.events import RunEnd, ToolResultEvent, TurnStart
from pagentv5.provider import (
    ProviderMessage,
    ResponseEnd,
    ResponseStart,
    TextDelta,
    ToolCallEnd,
    Usage,
)
from pagentv5.provider.tool_io import (
    ToolResultInput,
    append_tool_round,
    tools_for_api,
)


def usage() -> Usage:
    return Usage(input_tokens=1, output_tokens=1)


class SequencedProvider:
    api_protocol = "openai-completions"

    def __init__(self, responses: list[list[ProviderMessage]]) -> None:
        self.responses = responses
        self.requests: list[tuple[object, object]] = []

    async def complete(self, input, tools=None, **request_kwargs):
        del request_kwargs
        self.requests.append((input, tools))
        response = self.responses[len(self.requests) - 1]
        for message in response:
            yield message


@pytest.mark.asyncio
async def test_runner_executes_tool_and_feeds_result_to_next_turn():
    @tool()
    def add(a: int, b: int) -> int:
        return a + b

    provider = SequencedProvider(
        [
            [
                ResponseStart(response_id="response_1"),
                ToolCallEnd(
                    content_index=0,
                    tool_call_id="call_1",
                    name="add",
                    arguments='{"a":2,"b":3}',
                ),
                ResponseEnd(stop_reason="tool_use", usage=usage()),
            ],
            [
                ResponseStart(response_id="response_2"),
                TextDelta(content_index=0, delta="5"),
                ResponseEnd(stop_reason="stop", usage=usage()),
            ],
        ]
    )
    runner = Runner(provider, tools=[add])

    events = [
        event
        async for event in runner.run(
            [{"role": "user", "content": "add 2 and 3"}],
            run_id="run_1",
        )
    ]

    result = next(event for event in events if isinstance(event, ToolResultEvent))
    assert result.content == "5"
    assert result.ok is True
    assert result.turn_index == 0
    assert result.step_index == 1

    second_input, second_tools = provider.requests[1]
    assert second_input[-2] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "add",
                    "arguments": '{"a":2,"b":3}',
                },
            }
        ],
    }
    assert second_input[-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "5",
    }
    assert second_tools == provider.requests[0][1]
    assert events[-1] == RunEnd(
        run_id="run_1",
        stop_reason="completed",
        turn_count=2,
    )


@pytest.mark.asyncio
async def test_runner_returns_unknown_tool_error_to_model():
    provider = SequencedProvider(
        [
            [
                ToolCallEnd(
                    content_index=0,
                    tool_call_id="call_1",
                    name="missing",
                    arguments="{}",
                ),
                ResponseEnd(stop_reason="tool_use", usage=usage()),
            ],
            [
                TextDelta(content_index=0, delta="handled"),
                ResponseEnd(stop_reason="stop", usage=usage()),
            ],
        ]
    )

    events = [
        event
        async for event in Runner(provider).run(
            [{"role": "user", "content": "call it"}],
            run_id="run_1",
        )
    ]

    result = next(event for event in events if isinstance(event, ToolResultEvent))
    assert result.ok is False
    assert "unknown tool 'missing'" in result.content
    assert provider.requests[1][0][-1]["content"] == result.content


@pytest.mark.asyncio
async def test_runner_uses_tool_free_synthesis_after_max_turns():
    @tool()
    def lookup() -> str:
        return "context"

    provider = SequencedProvider(
        [
            [
                ToolCallEnd(
                    content_index=0,
                    tool_call_id="call_1",
                    name="lookup",
                    arguments="{}",
                ),
                ResponseEnd(stop_reason="tool_use", usage=usage()),
            ],
            [
                TextDelta(content_index=0, delta="summary"),
                ResponseEnd(stop_reason="stop", usage=usage()),
            ],
        ]
    )

    events = [
        event
        async for event in Runner(provider, tools=[lookup], max_turns=1).run(
            [{"role": "user", "content": "research"}],
            run_id="run_1",
        )
    ]

    turn_starts = [event for event in events if isinstance(event, TurnStart)]
    assert [event.synthesis for event in turn_starts] == [False, True]
    assert provider.requests[0][1] is not None
    assert provider.requests[1][1] is None
    assert events[-1].stop_reason == "completed"
    assert events[-1].turn_count == 2


def test_tool_schema_is_adapted_for_each_openai_api():
    schema = [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search docs",
                "parameters": {"type": "object"},
            },
        }
    ]

    assert tools_for_api(schema, "openai-completions") == schema
    assert tools_for_api(schema, "openai-responses") == [
        {
            "type": "function",
            "name": "search",
            "description": "Search docs",
            "parameters": {"type": "object"},
        }
    ]


def test_responses_tool_round_uses_function_call_items():
    call = ToolCallEnd(
        content_index=0,
        tool_call_id="call_1",
        name="search",
        arguments='{"q":"pagent"}',
    )

    input = append_tool_round(
        "find pagent",
        api_protocol="openai-responses",
        assistant_text="I will search.",
        tool_calls=[call],
        tool_results=[ToolResultInput(tool_call_id="call_1", content="found")],
    )

    assert input == [
        {"role": "user", "content": "find pagent"},
        {"role": "assistant", "content": "I will search."},
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "search",
            "arguments": '{"q":"pagent"}',
        },
        {
            "type": "function_call_output",
            "call_id": "call_1",
            "output": "found",
        },
    ]


@pytest.mark.asyncio
async def test_tool_rejects_non_object_arguments():
    @tool()
    def echo(value: str) -> str:
        return value

    output = await echo.acall('["value"]')

    assert output.ok is False
    assert output.content == "Tool arguments must be a JSON object"
