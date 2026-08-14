from collections.abc import AsyncIterable, AsyncIterator
from typing import cast

from openai.types.chat import ChatCompletionChunk
from openai.types.responses import ResponseStreamEvent

from ..messages import ProviderMessage
from .chat_completions import adapt_chat_completions
from .responses import adapt_responses

RawProviderEvent = ChatCompletionChunk | ResponseStreamEvent


def adapt_stream(
    api_protocol: str,
    stream: AsyncIterable[RawProviderEvent],
) -> AsyncIterator[ProviderMessage]:
    if api_protocol == "openai-completions":
        chat_stream = cast(AsyncIterable[ChatCompletionChunk], stream)
        return adapt_chat_completions(chat_stream)
    if api_protocol == "openai-responses":
        responses_stream = cast(AsyncIterable[ResponseStreamEvent], stream)
        return adapt_responses(responses_stream)
    raise ValueError(f"unsupported api_protocol {api_protocol!r}")
