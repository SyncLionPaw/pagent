import pytest
from pydantic import TypeAdapter, ValidationError

from pagentv5.provider import (
    ProviderMessage,
    ResponseEnd,
    TextDelta,
    ToolCallEnd,
    Usage,
)


def test_provider_message_uses_type_discriminator():
    message = TypeAdapter(ProviderMessage).validate_python(
        {
            "type": "text_delta",
            "content_index": 1,
            "delta": "hello",
        }
    )

    assert message == TextDelta(content_index=1, delta="hello")
    assert message.model_dump() == {
        "type": "text_delta",
        "content_index": 1,
        "delta": "hello",
    }


def test_provider_messages_are_frozen():
    message = TextDelta(content_index=0, delta="hello")

    with pytest.raises(ValidationError, match="frozen"):
        message.delta = "changed"


def test_provider_messages_reject_unknown_fields():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        TextDelta(content_index=0, delta="hello", unknown=True)


def test_content_index_must_be_non_negative():
    with pytest.raises(ValidationError):
        TextDelta(content_index=-1, delta="hello")


def test_tool_call_end_contains_complete_call():
    event = ToolCallEnd(
        content_index=2,
        tool_call_id="call_1",
        name="search",
        arguments='{"query":"pagent"}',
    )

    assert event.name == "search"
    assert event.arguments == '{"query":"pagent"}'


def test_response_end_contains_usage():
    event = ResponseEnd(
        stop_reason="tool_use",
        usage=Usage(input_tokens=10, output_tokens=4, reasoning_tokens=2),
    )

    assert event.usage.input_tokens == 10
    assert event.usage.reasoning_tokens == 2
    assert event.usage.cache_read_tokens == 0
