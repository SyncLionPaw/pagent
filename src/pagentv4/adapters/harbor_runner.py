"""Run pagentv4 inplace inside a Harbor task container."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
from pathlib import Path

from pagentv4 import AgentCore, CodeRunner, DeepSeek, Provider, RunEnd, TurnResult

SYSTEM_PROMPT = """You are a coding agent working directly in the current project.
Inspect the project and the user request, make the required changes, and run focused
tests or checks when useful. Use the available file and command tools to complete the
task. Keep changes scoped to the request. Do not only describe a patch: edit the files.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instruction-path", type=Path, required=True)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-turns", type=int, default=100)
    return parser.parse_args()


def model_id(model: str) -> str:
    return model.split("/", 1)[1] if "/" in model else model


def build_provider(model: str) -> Provider:
    base_url = os.getenv("PAGENT_BENCH_BASE_URL")
    if base_url:
        api_key = os.getenv("PAGENT_BENCH_API_KEY") or "not-needed"
        return Provider(model_id(model), base_url=base_url, apikey=api_key)
    if model.startswith("deepseek/"):
        return DeepSeek(model_id(model))
    return Provider(model_id(model))


def add_usage(total: dict[str, int], usage: dict | None) -> None:
    if not usage:
        return
    total["input_tokens"] += int(
        usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
    )
    total["output_tokens"] += int(
        usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
    )
    prompt_details = usage.get("prompt_tokens_details") or {}
    total["cache_tokens"] += int(prompt_details.get("cached_tokens", 0) or 0)


async def run() -> None:
    args = parse_args()
    args.logs_dir.mkdir(parents=True, exist_ok=True)
    project = Path.cwd().resolve()
    thread_root = args.logs_dir / "threads"
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_tokens": 0}
    stop_reason = "unknown"

    agent = AgentCore(
        build_provider(args.model),
        system=SYSTEM_PROMPT,
        max_turns=args.max_turns,
    )
    runner = CodeRunner(
        agent,
        backend="inplace",
        project_path=project,
        thread_id="harbor",
        root=thread_root,
        command_policy="open",
    )
    try:
        instruction = args.instruction_path.read_text()
        async for event in runner.run(instruction, return_type="event"):
            if isinstance(event, TurnResult):
                add_usage(usage, event.usage)
            elif isinstance(event, RunEnd):
                stop_reason = event.stop_reason
    finally:
        await runner.close()

    messages_path = thread_root / "harbor" / "messages" / "messages.jsonl"
    if messages_path.is_file():
        shutil.copy2(messages_path, args.logs_dir / "messages.jsonl")
    summary = {
        **usage,
        "stop_reason": stop_reason,
        "max_turns": args.max_turns,
        "model": args.model,
        "project": str(project),
    }
    (args.logs_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True)
    )


if __name__ == "__main__":
    asyncio.run(run())
