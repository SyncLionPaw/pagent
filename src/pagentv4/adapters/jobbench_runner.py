"""Run pagentv4 inplace as a JobBench agent.

JobBench drives one agent per task: it hands the agent a prompt that points at a
task folder, the agent reads the reference files, does the work, and writes the
final deliverables to an output directory. This module is that agent entry point
for pagentv4, mirroring how the OpenCode harness is invoked from
``eval/run_benchmark_opencode.sh``.

The surrounding shell script (``eval/run_benchmark_pagentv4.sh``) copies each task
into an isolated workspace under ``/tmp`` and passes it here as ``--project``.
pagentv4 runs in inplace mode against that workspace, so ``task_folder/`` and
``output/`` are plain relative paths the file tools can reach.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from pagentv4 import (
    AgentCore,
    CodeRunner,
    DeepSeek,
    Provider,
    RunEnd,
    encode_event_line,
)

SYSTEM_PROMPT = """You are a professional work agent operating directly inside \
the current project directory.

Read the task instructions and reference files, do the work the task asks for, \
and write the final deliverables to the output directory named in the prompt. \
Use the file tools for text and the run_command tool for anything else: parse \
xlsx / docx / pdf / db / pptx with Python (pandas, openpyxl, sqlite3, pdfplumber, \
python-docx) run through run_command, then write the results out.

Only put final deliverables in the output directory. Do not leave intermediate or \
scratch files there. When sources conflict, reason about the conflict explicitly \
and justify the choice you make in your deliverable."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="pagentv4 JobBench agent runner")
    parser.add_argument("--prompt", help="task prompt text")
    parser.add_argument(
        "--prompt-file", type=Path, help="read the task prompt from a file"
    )
    parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="workspace directory the agent operates in (inplace)",
    )
    parser.add_argument(
        "--model", required=True, help="model id, e.g. deepseek/deepseek-v4-flash"
    )
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument(
        "--api-max-retries",
        type=int,
        default=6,
        help="SDK-level retries for 429/5xx; raise it under high concurrency",
    )
    parser.add_argument(
        "--traj", type=Path, help="write the event trajectory as NDJSON here"
    )
    parser.add_argument(
        "--thread-id", default="jobbench", help="thread id for conversation storage"
    )
    return parser.parse_args()


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        return args.prompt
    if args.prompt_file is not None:
        return args.prompt_file.read_text()
    raise SystemExit("one of --prompt or --prompt-file is required")


def model_id(model: str) -> str:
    return model.split("/", 1)[1] if "/" in model else model


def build_provider(model: str, max_retries: int) -> Provider:
    import os

    base_url = os.getenv("PAGENT_BENCH_BASE_URL")
    if base_url:
        api_key = os.getenv("PAGENT_BENCH_API_KEY") or "not-needed"
        return Provider(
            model_id(model),
            base_url=base_url,
            apikey=api_key,
            max_retries=max_retries,
        )
    if model.startswith("deepseek/"):
        return DeepSeek(model_id(model), max_retries=max_retries)
    return Provider(model_id(model), max_retries=max_retries)


async def run() -> int:
    args = parse_args()
    prompt = read_prompt(args)
    project = args.project.expanduser().resolve()
    if not project.is_dir():
        raise SystemExit(f"--project is not a directory: {project}")

    traj = open(args.traj, "w", encoding="utf-8") if args.traj else None
    thread_root = project / ".pagent_threads"

    agent = AgentCore(
        build_provider(args.model, args.api_max_retries),
        system=SYSTEM_PROMPT,
        max_turns=args.max_turns,
    )
    runner = CodeRunner(
        agent,
        backend="inplace",
        project_path=project,
        thread_id=args.thread_id,
        root=thread_root,
        command_policy="open",
    )

    stop_reason = "unknown"
    try:
        async for event in runner.run(prompt, return_type="event"):
            if traj:
                traj.write(encode_event_line(event))
                traj.flush()
            if isinstance(event, RunEnd):
                stop_reason = event.stop_reason
    finally:
        await runner.close()
        if traj:
            traj.close()

    # cancelled is the only stop reason that means the run did not finish cleanly.
    return 1 if stop_reason == "cancelled" else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
