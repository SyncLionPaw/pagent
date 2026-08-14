from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from ..provider.messages import Usage

RunStopReason: TypeAlias = Literal[
    "completed",
    "empty_response",
    "max_turns",
    "cancelled",
    "error",
]
TurnStopReason: TypeAlias = RunStopReason | Literal["continuing"]
StepType: TypeAlias = Literal["model_generation", "tool_execution"]
StepStatus: TypeAlias = Literal["completed", "cancelled", "error"]


class RunnerEventBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    category: Literal["runner"] = "runner"
    run_id: str = Field(min_length=1)


class RunStart(RunnerEventBase):
    type: Literal["run_start"] = "run_start"
    trigger_type: str = Field(min_length=1)
    trigger_id: str | None = None


class RunEnd(RunnerEventBase):
    type: Literal["run_end"] = "run_end"
    stop_reason: RunStopReason
    turn_count: int = Field(ge=0)


class TurnStart(RunnerEventBase):
    type: Literal["turn_start"] = "turn_start"
    turn_index: int = Field(ge=0)
    synthesis: bool = False


class TurnEnd(RunnerEventBase):
    type: Literal["turn_end"] = "turn_end"
    turn_index: int = Field(ge=0)
    stop_reason: TurnStopReason


class StepStart(RunnerEventBase):
    type: Literal["step_start"] = "step_start"
    turn_index: int = Field(ge=0)
    step_index: int = Field(ge=0)
    step_type: StepType


class StepEnd(RunnerEventBase):
    type: Literal["step_end"] = "step_end"
    turn_index: int = Field(ge=0)
    step_index: int = Field(ge=0)
    step_type: StepType
    status: StepStatus


class StepEventBase(RunnerEventBase):
    turn_index: int = Field(ge=0)
    step_index: int = Field(ge=0)


class ModelEventBase(StepEventBase):
    pass


class ResponseStartEvent(ModelEventBase):
    type: Literal["response_start"] = "response_start"
    response_id: str | None = None


class TextStartEvent(ModelEventBase):
    type: Literal["text_start"] = "text_start"
    content_index: int = Field(ge=0)


class TextDeltaEvent(ModelEventBase):
    type: Literal["text_delta"] = "text_delta"
    content_index: int = Field(ge=0)
    delta: str


class TextEndEvent(ModelEventBase):
    type: Literal["text_end"] = "text_end"
    content_index: int = Field(ge=0)
    text: str


class ReasoningStartEvent(ModelEventBase):
    type: Literal["reasoning_start"] = "reasoning_start"
    content_index: int = Field(ge=0)


class ReasoningDeltaEvent(ModelEventBase):
    type: Literal["reasoning_delta"] = "reasoning_delta"
    content_index: int = Field(ge=0)
    delta: str


class ReasoningEndEvent(ModelEventBase):
    type: Literal["reasoning_end"] = "reasoning_end"
    content_index: int = Field(ge=0)
    text: str


class ToolCallStartEvent(ModelEventBase):
    type: Literal["tool_call_start"] = "tool_call_start"
    content_index: int = Field(ge=0)
    tool_call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class ToolCallDeltaEvent(ModelEventBase):
    type: Literal["tool_call_delta"] = "tool_call_delta"
    content_index: int = Field(ge=0)
    tool_call_id: str = Field(min_length=1)
    arguments_delta: str


class ToolCallEndEvent(ModelEventBase):
    type: Literal["tool_call_end"] = "tool_call_end"
    content_index: int = Field(ge=0)
    tool_call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    arguments: str


class ToolResultEvent(StepEventBase):
    type: Literal["tool_result"] = "tool_result"
    tool_call_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    content: str
    ok: bool = True


class ResponseEndEvent(ModelEventBase):
    type: Literal["response_end"] = "response_end"
    stop_reason: Literal["stop", "length", "tool_use"]
    usage: Usage


class ResponseErrorEvent(ModelEventBase):
    type: Literal["response_error"] = "response_error"
    reason: Literal["error", "cancelled"]
    message: str
    code: str | None = None


RunnerEvent: TypeAlias = Annotated[
    RunStart
    | RunEnd
    | TurnStart
    | TurnEnd
    | StepStart
    | StepEnd
    | ResponseStartEvent
    | TextStartEvent
    | TextDeltaEvent
    | TextEndEvent
    | ReasoningStartEvent
    | ReasoningDeltaEvent
    | ReasoningEndEvent
    | ToolCallStartEvent
    | ToolCallDeltaEvent
    | ToolCallEndEvent
    | ToolResultEvent
    | ResponseEndEvent
    | ResponseErrorEvent,
    Field(discriminator="type"),
]
