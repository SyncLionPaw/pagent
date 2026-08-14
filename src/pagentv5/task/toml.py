import json
import re
import tomllib
from pathlib import Path
from typing import Any

BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def toml_key(value: str) -> str:
    if BARE_KEY.fullmatch(value):
        return value
    return json.dumps(value, ensure_ascii=False)


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value: {type(value).__name__}")


def render_table(
    path: tuple[str, ...],
    values: dict[str, Any],
    blocks: list[str],
) -> None:
    scalar_lines = [
        f"{toml_key(key)} = {toml_value(value)}"
        for key, value in values.items()
        if value is not None and not isinstance(value, dict)
    ]
    if scalar_lines:
        heading = ".".join(toml_key(part) for part in path)
        blocks.append("\n".join([f"[{heading}]", *scalar_lines]))

    for key, value in values.items():
        if isinstance(value, dict) and value:
            render_table((*path, key), value, blocks)


def dump_task_toml(payload: dict[str, Any]) -> str:
    blocks: list[str] = []
    for section, values in payload.items():
        if isinstance(values, dict) and values:
            render_table((section,), values, blocks)
    return "\n\n".join(blocks) + "\n"


def load_task_toml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("rb") as file:
        return tomllib.load(file)
