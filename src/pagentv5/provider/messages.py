from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class ProviderMessageBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Usage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)


class ResponseStart(ProviderMessageBase):
    type: Literal["response_start"] = "response_start"
    response_id: str | None = None


class TextStart(ProviderMessageBase):
    type: Literal["text_start"] = "text_start"
    content_index: int = Field(ge=0)


class TextDelta(ProviderMessageBase):
    type: Literal["text_delta"] = "text_delta"
    content_index: int = Field(ge=0)
    delta: str


class TextEnd(ProviderMessageBase):
    type: Literal["text_end"] = "text_end"
    content_index: int = Field(ge=0)
    text: str


class ReasoningStart(ProviderMessageBase):
    type: Literal["reasoning_start"] = "reasoning_start"
    content_index: int = Field(ge=0)


class ReasoningDelta(ProviderMessageBase):
    type: Literal["reasoning_delta"] = "reasoning_delta"
    content_index: int = Field(ge=0)
    delta: str


class ReasoningEnd(ProviderMessageBase):
    type: Literal["reasoning_end"] = "reasoning_end"
    content_index: int = Field(ge=0)
    text: str


class ToolCallStart(ProviderMessageBase):
    type: Literal["tool_call_start"] = "tool_call_start"
    content_index: int = Field(ge=0)
    tool_call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class ToolCallDelta(ProviderMessageBase):
    type: Literal["tool_call_delta"] = "tool_call_delta"
    content_index: int = Field(ge=0)
    tool_call_id: str = Field(min_length=1)
    arguments_delta: str


class ToolCallEnd(ProviderMessageBase):
    type: Literal["tool_call_end"] = "tool_call_end"
    content_index: int = Field(ge=0)
    tool_call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: str


class ResponseEnd(ProviderMessageBase):
    type: Literal["response_end"] = "response_end"
    stop_reason: Literal["stop", "length", "tool_use"]
    usage: Usage


class ResponseError(ProviderMessageBase):
    type: Literal["response_error"] = "response_error"
    reason: Literal["error", "cancelled"]
    message: str
    code: str | None = None


ProviderMessage: TypeAlias = Annotated[
    ResponseStart
    | TextStart
    | TextDelta
    | TextEnd
    | ReasoningStart
    | ReasoningDelta
    | ReasoningEnd
    | ToolCallStart
    | ToolCallDelta
    | ToolCallEnd
    | ResponseEnd
    | ResponseError,
    Field(discriminator="type"),
]
