"""Function tools for pagentv5.

`@tool` turns a plain function into a `FunctionTool`: it derives the JSON schema
from the signature and docstring, renders the OpenAI tool dict, and runs the
call with argument parsing and error capture. Adapted from pagentv4; the code
is model-agnostic and carries no runtime coupling.
"""

import inspect
import json
import types
from collections.abc import Mapping
from dataclasses import dataclass
from functools import reduce
from typing import Any, Union, get_args, get_origin, get_type_hints

from docstring_parser import parse


@dataclass(frozen=True, slots=True)
class ToolOutput:
    content: str
    ok: bool = True

    @classmethod
    def succeed(cls, content: str) -> "ToolOutput":
        return cls(content=str(content), ok=True)

    @classmethod
    def fail(cls, message: str) -> "ToolOutput":
        return cls(content=str(message), ok=False)


def normalize_tool_output(value: Any) -> ToolOutput:
    if isinstance(value, ToolOutput):
        return value
    return ToolOutput.succeed(value)


def func_wants_context(func: Any) -> bool:
    """Whether func declares a `context` parameter for the runner to inject."""
    if func is None:
        return False
    return "context" in inspect.signature(func).parameters


class FunctionTool:
    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        func: Any = None,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func
        self.wants_context = func_wants_context(func)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def parse_arguments(
        self, arguments: Any
    ) -> tuple[dict[str, Any] | None, ToolOutput | None]:
        """Normalize tool arguments into kwargs; on failure return (None, error)."""
        if arguments is None:
            return {}, None
        if not isinstance(arguments, str):
            if isinstance(arguments, Mapping):
                return dict(arguments), None
            return None, ToolOutput.fail("Tool arguments must be a JSON object")
        stripped = arguments.strip()
        if not stripped:
            return {}, None
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as e:
            return None, ToolOutput.fail(f"Invalid JSON in tool arguments: {e}")
        if not isinstance(payload, dict):
            return None, ToolOutput.fail("Tool arguments must be a JSON object")
        return payload, None

    def build_kwargs(
        self, arguments: Any, context: Any
    ) -> tuple[dict[str, Any] | None, ToolOutput | None]:
        kwargs, error = self.parse_arguments(arguments)
        if error is not None:
            return None, error
        if self.wants_context:
            kwargs["context"] = context
        return kwargs, None

    def call(self, arguments: Any = None, *, context: Any = None) -> ToolOutput:
        if self.func is None:
            return ToolOutput.fail(f"tool {self.name} has no bound function")
        if inspect.iscoroutinefunction(self.func):
            return ToolOutput.fail(f"tool {self.name!r} is async; use acall() instead")

        kwargs, error = self.build_kwargs(arguments, context)
        if error is not None:
            return error
        try:
            return normalize_tool_output(self.func(**kwargs))
        except Exception as e:
            return ToolOutput.fail(f"{self.name} error: {e}")

    async def acall(self, arguments: Any = None, *, context: Any = None) -> ToolOutput:
        if self.func is None:
            return ToolOutput.fail(f"tool {self.name} has no bound function")

        kwargs, error = self.build_kwargs(arguments, context)
        if error is not None:
            return error
        try:
            result = self.func(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return normalize_tool_output(result)
        except Exception as e:
            return ToolOutput.fail(f"{self.name} error: {e}")


def unwrap_optional(type_hint: Any) -> tuple[bool, Any]:
    origin = get_origin(type_hint)
    # Accept both typing.Union and PEP 604 `int | None` (types.UnionType).
    if origin is not Union and origin is not types.UnionType:
        return False, type_hint

    args = get_args(type_hint)
    if type(None) not in args:
        return False, type_hint

    non_none_args = [arg for arg in args if arg is not type(None)]
    if len(non_none_args) == 1:
        return True, non_none_args[0]
    return True, reduce(lambda x, y: x | y, non_none_args)


def type_to_schema(type_hint: Any) -> dict[str, Any]:
    origin = get_origin(type_hint)
    if origin is list:
        args = get_args(type_hint)
        item_type = args[0] if args else Any
        return {"type": "array", "items": type_to_schema(item_type)}
    if origin is dict:
        return {"type": "object"}
    if type_hint is str:
        return {"type": "string"}
    if type_hint is int:
        return {"type": "integer"}
    if type_hint is float:
        return {"type": "number"}
    if type_hint is bool:
        return {"type": "boolean"}
    return {"type": "string"}


def extract_function_schema(
    func: Any,
    name_override: str | None = None,
    description_override: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    func_name = name_override or func.__name__
    sig = inspect.signature(func)
    docstring = parse(func.__doc__ or "")
    description = description_override or docstring.short_description
    param_docs = {param.arg_name: param.description for param in docstring.params}
    type_hints = get_type_hints(func)

    properties: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls", "context"):
            continue

        param_type = type_hints.get(param_name, Any)
        param_desc = param_docs.get(param_name)
        is_optional, base_type = unwrap_optional(param_type)
        schema = type_to_schema(base_type)
        if param_desc:
            schema["description"] = param_desc
        properties[param_name] = schema

        if param.default == inspect.Parameter.empty and not is_optional:
            required.append(param_name)

    json_schema = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
    return func_name, description or "", json_schema


def tool(name: str | None = None, description: str | None = None):
    def decorator(func: Any) -> FunctionTool:
        func_name, func_description, parameters = extract_function_schema(
            func,
            name_override=name,
            description_override=description,
        )
        return FunctionTool(
            name=func_name,
            description=func_description,
            parameters=parameters,
            func=func,
        )

    return decorator


def to_openai_tools(tools: list[FunctionTool]) -> list[dict[str, Any]]:
    return [ft.to_dict() for ft in tools]
