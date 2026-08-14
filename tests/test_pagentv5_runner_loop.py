from collections.abc import AsyncIterator

import pytest
from openai.types.chat import ChatCompletionChunk

from pagentv5 import tool
from pagentv5.events import RunEnd, ToolCallEndEvent, ToolResultEvent
from pagentv5.provider import Provider
from pagentv5.runtime import Runner
from pagentv5.session import MemorySessionBackend, Session


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


async def native_stream(
    *chunks: ChatCompletionChunk,
) -> AsyncIterator[ChatCompletionChunk]:
    for chunk in chunks:
        yield chunk


def make_provider(
    monkeypatch,
    chunks: list[ChatCompletionChunk],
    *,
    subsequent_chunks: list[ChatCompletionChunk] | None = None,
) -> Provider:
    provider = Provider(
        "test-model",
        api_protocol="openai-completions",
        base_url="https://example.test/v1",
        api_key="unit-test",
    )

    request_count = 0

    async def fake_create_chat_completion(messages, tools, request_kwargs):
        nonlocal request_count
        del messages, tools, request_kwargs
        selected = (
            subsequent_chunks
            if request_count > 0 and subsequent_chunks is not None
            else chunks
        )
        request_count += 1
        return native_stream(*selected)

    monkeypatch.setattr(provider, "create_chat_completion", fake_create_chat_completion)
    return provider


@pytest.mark.asyncio
async def test_runner_loop_over_real_provider_text(monkeypatch):
    provider = make_provider(
        monkeypatch,
        [
            chat_chunk(delta={"content": "hel"}),
            chat_chunk(
                delta={"content": "lo"},
                finish_reason="stop",
                usage={"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            ),
        ],
    )
    runner = Runner(provider)

    events = [
        event
        async for event in runner.run(
            [{"role": "user", "content": "hi"}],
            run_id="run_1",
        )
    ]

    assert [event.type for event in events] == [
        "run_start",
        "turn_start",
        "step_start",
        "response_start",
        "text_start",
        "text_delta",
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
    assert runner.run_in_progress is False


@pytest.mark.asyncio
async def test_runner_loop_over_real_provider_tool_call(monkeypatch):
    @tool()
    def search(q: str) -> str:
        return f"found {q}"

    provider = make_provider(
        monkeypatch,
        [
            chat_chunk(
                delta={
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": "search", "arguments": '{"q":'},
                        }
                    ]
                }
            ),
            chat_chunk(
                delta={
                    "tool_calls": [{"index": 0, "function": {"arguments": '"pagent"}'}}]
                },
                finish_reason="tool_calls",
            ),
        ],
        subsequent_chunks=[
            chat_chunk(
                delta={"content": "found pagent"},
                finish_reason="stop",
                usage={"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10},
            ),
        ],
    )
    runner = Runner(provider, tools=[search])

    events = [
        event
        async for event in runner.run(
            [{"role": "user", "content": "search pagent"}],
            run_id="run_1",
        )
    ]

    tool_end = next(e for e in events if isinstance(e, ToolCallEndEvent))
    assert tool_end.name == "search"
    assert tool_end.arguments == '{"q":"pagent"}'
    tool_result = next(e for e in events if isinstance(e, ToolResultEvent))
    assert tool_result.content == "found pagent"
    assert tool_result.ok is True
    assert isinstance(events[-1], RunEnd)
    assert events[-1].stop_reason == "completed"
    assert events[-1].turn_count == 2


@pytest.mark.asyncio
async def test_runner_loop_is_reusable_across_runs(monkeypatch):
    provider = make_provider(
        monkeypatch,
        [
            chat_chunk(
                delta={"content": "hi"},
                finish_reason="stop",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            ),
        ],
    )
    runner = Runner(provider)

    first = [
        e async for e in runner.run([{"role": "user", "content": "a"}], run_id="r1")
    ]
    assert runner.run_in_progress is False
    assert isinstance(first[-1], RunEnd)

    second = [
        e async for e in runner.run([{"role": "user", "content": "b"}], run_id="r2")
    ]
    assert isinstance(second[-1], RunEnd)
    assert second[0].run_id == "r2"
    assert runner.run_in_progress is False


@pytest.mark.asyncio
async def test_runner_owns_session_transcript(monkeypatch):
    captured_inputs: list[list[dict]] = []
    provider = make_provider(
        monkeypatch,
        [
            chat_chunk(
                delta={"content": "hello"},
                finish_reason="stop",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            )
        ],
    )

    async def capture_chat_completion(messages, tools, request_kwargs):
        del tools, request_kwargs
        captured_inputs.append(messages)
        return native_stream(
            chat_chunk(
                delta={"content": "hello"},
                finish_reason="stop",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            )
        )

    monkeypatch.setattr(
        provider,
        "create_chat_completion",
        capture_chat_completion,
    )
    session = Session("messages", MemorySessionBackend())
    session.append({"role": "system", "content": "Be concise."})
    runner = Runner(provider, session=session)

    _ = [event async for event in runner.run("hi")]

    assert captured_inputs == [
        [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "hi"},
        ]
    ]
    assert session.messages == [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
