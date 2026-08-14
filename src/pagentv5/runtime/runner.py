import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Collection
from typing import Any, TypeAlias
from uuid import uuid4

from ..events import runner as runner_events
from ..provider import messages as provider_messages
from ..provider.provider import ProviderInput, ProviderProtocol
from ..provider.tool_io import (
    ToolResultInput,
    append_assistant_response,
    append_tool_round,
)
from ..tools import FunctionTool, ToolOutput, to_openai_tools
from .event_translation import event_is_selected, translate_provider_message
from .model_step import ModelStep
from .state import RunnerState

ToolApproval: TypeAlias = Callable[
    [provider_messages.ToolCallEnd],
    bool | Awaitable[bool],
]


def provider_api_protocol(
    provider: ProviderProtocol,
    input: ProviderInput,
) -> str:
    api_protocol = getattr(provider, "api_protocol", None)
    if isinstance(api_protocol, str):
        return api_protocol
    if isinstance(input, str):
        return "openai-responses"
    return "openai-completions"


class Runner:
    """Runs model generation and tool execution until the task stops."""

    def __init__(
        self,
        provider: ProviderProtocol,
        *,
        tools: list[FunctionTool] | None = None,
        max_turns: int = 24,
        event_types: Collection[str] | None = None,
        require_tool_approval: bool = False,
        approve_tool: ToolApproval | None = None,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")

        self.provider = provider
        self.state = RunnerState()
        self.tools: list[FunctionTool] = []
        self.tool_map: dict[str, FunctionTool] = {}
        self.tool_schemas: list[dict[str, Any]] | None = None
        self.set_tools(tools or [])
        self.max_turns = max_turns
        self.event_types = frozenset(event_types) if event_types is not None else None
        self.require_tool_approval = require_tool_approval
        self.approve_tool = approve_tool
        self.last_input: ProviderInput | None = None

    @property
    def run_in_progress(self) -> bool:
        return self.state.busy

    def selects(self, event: runner_events.RunnerEvent) -> bool:
        return event_is_selected(event, self.event_types)

    def set_tools(self, tools: Collection[FunctionTool]) -> None:
        if self.run_in_progress:
            raise RuntimeError("cannot change tools while a run is in progress")
        selected = list(tools)
        tool_names = [tool.name for tool in selected]
        if len(tool_names) != len(set(tool_names)):
            raise ValueError(f"duplicate tool names: {tool_names}")
        self.tools = selected
        self.tool_map = {tool.name: tool for tool in selected}
        self.tool_schemas = to_openai_tools(selected) or None

    async def execute_tool(
        self,
        tool_call: provider_messages.ToolCallEnd,
    ) -> ToolOutput:
        tool = self.tool_map.get(tool_call.name)
        if tool is None:
            return ToolOutput.fail(
                f"error: unknown tool {tool_call.name!r}; "
                f"available: {sorted(self.tool_map)}"
            )
        if self.require_tool_approval:
            if self.approve_tool is None:
                return ToolOutput.fail(
                    f"tool {tool_call.name!r} requires approval; "
                    "configure approve_tool or disable require_tool_approval"
                )
            approved = self.approve_tool(tool_call)
            if inspect.isawaitable(approved):
                approved = await approved
            if not approved:
                return ToolOutput.fail(f"tool {tool_call.name!r} was denied")
        return await tool.acall(tool_call.arguments, context=self)

    async def run(
        self,
        input: ProviderInput,
        *,
        trigger_type: str = "user",
        trigger_id: str | None = None,
        run_id: str | None = None,
        **request_kwargs: Any,
    ) -> AsyncIterator[runner_events.RunnerEvent]:
        if self.run_in_progress:
            raise RuntimeError("runner already has a run in progress")

        state = self.state
        state.begin_run(run_id or uuid4().hex)
        current_input = input
        self.last_input = current_input
        api_protocol = provider_api_protocol(self.provider, input)
        synthesis = False

        try:
            run_start = runner_events.RunStart(
                run_id=state.run_id,
                trigger_type=trigger_type,
                trigger_id=trigger_id,
            )
            if self.selects(run_start):
                yield run_start

            while True:
                turn_start = runner_events.TurnStart(
                    run_id=state.run_id,
                    turn_index=state.turn_index,
                    synthesis=synthesis,
                )
                model_start = runner_events.StepStart(
                    **state.context().fields(),
                    step_type="model_generation",
                )
                for event in (turn_start, model_start):
                    if self.selects(event):
                        yield event

                model_step = ModelStep()
                schemas = None if synthesis else self.tool_schemas
                try:
                    async for message in self.provider.complete(
                        current_input,
                        tools=schemas,
                        **request_kwargs,
                    ):
                        model_step.add(message)
                        event = translate_provider_message(message, state.context())
                        if self.selects(event):
                            yield event
                except Exception as error:
                    async for event in self.end_with_error(error):
                        yield event
                    return

                if model_step.terminal is None:
                    async for event in self.end_with_error(
                        RuntimeError(
                            "provider stream ended without a terminal message"
                        ),
                        code="provider_protocol_error",
                    ):
                        yield event
                    return

                if isinstance(
                    model_step.terminal,
                    provider_messages.ResponseError,
                ):
                    terminal = model_step.terminal
                    status: runner_events.StepStatus = (
                        "cancelled" if terminal.reason == "cancelled" else "error"
                    )
                    stop_reason: runner_events.RunStopReason = (
                        "cancelled" if terminal.reason == "cancelled" else "error"
                    )
                    async for event in self.end_current_turn(
                        step_type="model_generation",
                        status=status,
                        stop_reason=stop_reason,
                    ):
                        yield event
                    return

                model_end = runner_events.StepEnd(
                    **state.context().fields(),
                    step_type="model_generation",
                    status="completed",
                )
                if self.selects(model_end):
                    yield model_end

                if not model_step.tool_calls:
                    current_input = append_assistant_response(
                        current_input,
                        text=model_step.assistant_text(),
                    )
                    self.last_input = current_input
                    stop_reason: runner_events.RunStopReason = (
                        "completed" if model_step.has_output else "empty_response"
                    )
                    async for event in self.finish_run(stop_reason):
                        yield event
                    return

                if synthesis:
                    async for event in self.finish_run("max_turns"):
                        yield event
                    return

                state.advance_step()
                tool_start = runner_events.StepStart(
                    **state.context().fields(),
                    step_type="tool_execution",
                )
                if self.selects(tool_start):
                    yield tool_start

                tool_results: list[ToolResultInput] = []
                for tool_call in model_step.tool_calls:
                    output = await self.execute_tool(tool_call)
                    tool_results.append(
                        ToolResultInput(
                            tool_call_id=tool_call.tool_call_id,
                            content=output.content,
                        )
                    )
                    result_event = runner_events.ToolResultEvent(
                        **state.context().fields(),
                        tool_call_id=tool_call.tool_call_id,
                        name=tool_call.name,
                        content=output.content,
                        ok=output.ok,
                    )
                    if self.selects(result_event):
                        yield result_event

                tool_end = runner_events.StepEnd(
                    **state.context().fields(),
                    step_type="tool_execution",
                    status="completed",
                )
                if self.selects(tool_end):
                    yield tool_end

                current_input = append_tool_round(
                    current_input,
                    api_protocol=api_protocol,
                    assistant_text=model_step.assistant_text(),
                    tool_calls=model_step.tool_calls,
                    tool_results=tool_results,
                )
                self.last_input = current_input

                turn_end = runner_events.TurnEnd(
                    run_id=state.run_id,
                    turn_index=state.turn_index,
                    stop_reason="continuing",
                )
                if self.selects(turn_end):
                    yield turn_end

                synthesis = state.turn_index + 1 >= self.max_turns
                state.advance_turn()
        finally:
            if state.busy:
                state.end_run("error")

    async def end_with_error(
        self,
        error: Exception,
        *,
        code: str | None = None,
    ) -> AsyncIterator[runner_events.RunnerEvent]:
        error_event = runner_events.ResponseErrorEvent(
            **self.state.context().fields(),
            reason="error",
            message=str(error),
            code=code or type(error).__name__,
        )
        if self.selects(error_event):
            yield error_event
        async for event in self.end_current_turn(
            step_type="model_generation",
            status="error",
            stop_reason="error",
        ):
            yield event

    async def end_current_turn(
        self,
        *,
        step_type: runner_events.StepType,
        status: runner_events.StepStatus,
        stop_reason: runner_events.RunStopReason,
    ) -> AsyncIterator[runner_events.RunnerEvent]:
        step_end = runner_events.StepEnd(
            **self.state.context().fields(),
            step_type=step_type,
            status=status,
        )
        if self.selects(step_end):
            yield step_end
        async for event in self.finish_run(stop_reason):
            yield event

    async def finish_run(
        self,
        stop_reason: runner_events.RunStopReason,
    ) -> AsyncIterator[runner_events.RunnerEvent]:
        state = self.state
        turn_index = state.turn_index
        run_id = state.run_id
        state.end_run(stop_reason)
        events: tuple[runner_events.RunnerEvent, ...] = (
            runner_events.TurnEnd(
                run_id=run_id,
                turn_index=turn_index,
                stop_reason=stop_reason,
            ),
            runner_events.RunEnd(
                run_id=run_id,
                stop_reason=stop_reason,
                turn_count=turn_index + 1,
            ),
        )
        for event in events:
            if self.selects(event):
                yield event
