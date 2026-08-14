import os
from collections.abc import AsyncIterator, Mapping
from typing import Any, Protocol, TypeAlias

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import ChatCompletionChunk
from openai.types.responses import ResponseStreamEvent

from .adapter import adapt_stream
from .catalog import PROVIDER_CATALOG
from .messages import ProviderMessage
from .tool_io import tools_for_api

ProviderInput: TypeAlias = str | list[dict[str, Any]]
ProviderStream: TypeAlias = AsyncIterator[ProviderMessage]

RESERVED_REQUEST_KEYS = frozenset({"input", "messages", "model", "stream", "tools"})
IMPLEMENTED_API_PROTOCOLS = frozenset({"openai-completions", "openai-responses"})


class ProviderProtocol(Protocol):
    def complete(
        self,
        input: ProviderInput,
        tools: list[dict[str, Any]] | None = None,
        **request_kwargs: Any,
    ) -> ProviderStream: ...


def check_request_kwargs(kwargs: Mapping[str, Any]) -> None:
    reserved = kwargs.keys() & RESERVED_REQUEST_KEYS
    if reserved:
        raise TypeError(
            f"request kwargs must not include {sorted(reserved)}; "
            f"reserved keys: {sorted(RESERVED_REQUEST_KEYS)}"
        )


def resolve_api_key(
    *,
    explicit: str | None,
    env_name: str | None,
    required: bool,
) -> str:
    if explicit is not None and explicit.strip():
        return explicit.strip()
    if env_name is not None:
        api_key = os.getenv(env_name)
        if api_key is not None and api_key.strip():
            return api_key.strip()
    if required:
        raise ValueError(f"missing API key; set {env_name} or pass api_key")
    return "not-needed"


class Provider:
    def __init__(
        self,
        model_id: str,
        *,
        provider_id: str | None = None,
        api_protocol: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        request_kwargs: Mapping[str, Any] | None = None,
        max_retries: int | None = None,
    ) -> None:
        normalized_model_id = model_id.strip()
        if not normalized_model_id:
            raise ValueError("model_id must not be empty")

        normalized_provider_id = None
        spec = None
        if provider_id is not None:
            normalized_provider_id = provider_id.strip().lower()
            spec = PROVIDER_CATALOG.get(normalized_provider_id)
            if spec is None:
                raise ValueError(
                    f"unknown provider id {provider_id!r}; "
                    f"expected one of {sorted(PROVIDER_CATALOG)}"
                )

        selected_api_protocol = api_protocol
        if selected_api_protocol is None and spec is not None:
            selected_api_protocol = spec["api_protocol"]
        if selected_api_protocol is None:
            raise ValueError("api_protocol is required when provider_id is omitted")
        if selected_api_protocol not in IMPLEMENTED_API_PROTOCOLS:
            raise ValueError(
                f"unsupported api_protocol {selected_api_protocol!r}; "
                f"expected one of {sorted(IMPLEMENTED_API_PROTOCOLS)}"
            )

        selected_base_url = base_url
        if selected_base_url is None and spec is not None:
            selected_base_url = spec["base_url"]
        if selected_base_url is None:
            raise ValueError("base_url is required when provider_id is omitted")
        resolved_base_url = selected_base_url.strip()
        if not resolved_base_url:
            raise ValueError("base_url must not be empty")

        resolved_api_key = resolve_api_key(
            explicit=api_key,
            env_name=spec["api_key_env"] if spec else None,
            required=spec["api_key_required"] if spec else False,
        )
        resolved_request_kwargs = dict(request_kwargs or {})
        check_request_kwargs(resolved_request_kwargs)

        client_kwargs: dict[str, Any] = {
            "api_key": resolved_api_key,
            "base_url": resolved_base_url,
        }
        if max_retries is not None:
            client_kwargs["max_retries"] = max_retries

        self.provider_id = normalized_provider_id
        self.model_id = normalized_model_id
        self.api_protocol = selected_api_protocol
        self.base_url = resolved_base_url
        self.api_key = resolved_api_key
        self.request_kwargs = resolved_request_kwargs
        self.client = AsyncOpenAI(**client_kwargs)

    async def complete(
        self,
        input: ProviderInput,
        tools: list[dict[str, Any]] | None = None,
        **request_kwargs: Any,
    ) -> ProviderStream:
        check_request_kwargs(request_kwargs)
        kwargs = {**self.request_kwargs, **request_kwargs}
        api_tools = tools_for_api(tools, self.api_protocol)

        if self.api_protocol == "openai-responses":
            stream = await self.create_response(input, api_tools, kwargs)
        else:
            if isinstance(input, str):
                raise TypeError("chat_completions input must be a list of messages")
            stream = await self.create_chat_completion(input, api_tools, kwargs)

        async for message in adapt_stream(self.api_protocol, stream):
            yield message

    async def create_response(
        self,
        input: ProviderInput,
        tools: list[dict[str, Any]] | None,
        request_kwargs: dict[str, Any],
    ) -> AsyncStream[ResponseStreamEvent]:
        kwargs = {
            **request_kwargs,
            "model": self.model_id,
            "input": input,
            "stream": True,
        }
        if tools is not None:
            kwargs["tools"] = tools
        return await self.client.responses.create(**kwargs)

    async def create_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        request_kwargs: dict[str, Any],
    ) -> AsyncStream[ChatCompletionChunk]:
        kwargs = {
            **request_kwargs,
            "model": self.model_id,
            "messages": messages,
            "stream": True,
        }
        if tools is not None:
            kwargs["tools"] = tools

        stream_options = dict(kwargs.get("stream_options") or {})
        stream_options.setdefault("include_usage", True)
        kwargs["stream_options"] = stream_options
        return await self.client.chat.completions.create(**kwargs)
