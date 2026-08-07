import types
from types import SimpleNamespace

import pytest

from pagentv4 import (
    Agent,
    ToolCallArgsDelta,
    ToolCallBegin,
    ToolCallClaimBegin,
    ToolCallClaimEnd,
    ToolResult,
    TurnResult,
    VanillaRunner,
    tool,
)
from pagentv4.adapters import decode_event_line, encode_event_line


class FakeStreamChunk:
    def __init__(self, *, content=None, reasoning=None, tool_calls=None):
        delta = types.SimpleNamespace(
            content=content,
            reasoning_content=reasoning,
            tool_calls=tool_calls,
        )
        self.choices = [types.SimpleNamespace(delta=delta)]


class FakeProvider:
    def __init__(self, steps):
        self.steps = list(steps)

    async def complete(self, messages, tools=None, **run_kwargs):
        del messages, tools, run_kwargs
        chunks = self.steps.pop(0)

        async def stream():
            for chunk in chunks:
                yield chunk

        return stream()


@tool()
def echo(msg: str) -> str:
    """Echo back."""
    return msg


def tool_delta(*, index=0, id=None, name=None, arguments=None):
    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id, type="function", function=function)


@pytest.mark.asyncio
async def test_tool_call_claim_stream_events_before_execution():
    provider = FakeProvider(
        [
            [
                FakeStreamChunk(
                    tool_calls=[tool_delta(id="c1", name="echo", arguments=None)]
                ),
                FakeStreamChunk(tool_calls=[tool_delta(arguments='{"msg":')]),
                FakeStreamChunk(tool_calls=[tool_delta(arguments='"ping"}')]),
            ],
            [FakeStreamChunk(content="done")],
        ]
    )
    runner = VanillaRunner(Agent(provider, system="test", tools=[echo], max_turns=4))

    events = [event async for event in runner.run("go", return_type="event")]

    claim_begin = next(e for e in events if isinstance(e, ToolCallClaimBegin))
    assert claim_begin == ToolCallClaimBegin("c1", "echo", 0)

    args_deltas = [e for e in events if isinstance(e, ToolCallArgsDelta)]
    assert args_deltas == [
        ToolCallArgsDelta("c1", '{"msg":'),
        ToolCallArgsDelta("c1", '"ping"}'),
    ]

    claim_end = next(e for e in events if isinstance(e, ToolCallClaimEnd))
    assert claim_end == ToolCallClaimEnd("c1")

    turn_result_idx = next(i for i, e in enumerate(events) if isinstance(e, TurnResult))
    claim_end_idx = next(
        i for i, e in enumerate(events) if isinstance(e, ToolCallClaimEnd)
    )
    begin_idx = next(i for i, e in enumerate(events) if isinstance(e, ToolCallBegin))
    result_idx = next(i for i, e in enumerate(events) if isinstance(e, ToolResult))

    assert claim_end_idx < turn_result_idx < begin_idx < result_idx
    assert events[begin_idx].arguments == '{"msg":"ping"}'

    # Claim drafts must not pollute persisted assistant history.
    tool_msgs = [
        m
        for m in runner.messages.data
        if m.role == "assistant" and getattr(m.content, "type", None) == "function"
    ]
    assert len(tool_msgs) == 1
    assert tool_msgs[0].content.arguments == '{"msg":"ping"}'


@pytest.mark.asyncio
async def test_tool_call_claim_events_ignored_by_text_projection():
    tc = tool_delta(id="c1", name="echo", arguments='{"msg":"ping"}')
    provider = FakeProvider(
        [
            [FakeStreamChunk(tool_calls=[tc])],
            [FakeStreamChunk(content="done")],
        ]
    )
    runner = VanillaRunner(Agent(provider, system="test", tools=[echo], max_turns=4))
    text = [chunk async for chunk in runner.run("go", return_type="text")]
    assert text == ["done"]


def test_tool_call_claim_wire_roundtrip():
    events = [
        ToolCallClaimBegin("c1", "echo", 0),
        ToolCallArgsDelta("c1", '{"msg":"x"}'),
        ToolCallClaimEnd("c1"),
    ]
    for event in events:
        assert decode_event_line(encode_event_line(event)) == event
