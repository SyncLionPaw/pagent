"""Per-user pagentv4 Runner management for cloud backend."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from pagentv4.adapters.acp import encode_event_line
from pagentv4.core.provider import DeepSeek
from pagentv4.runtime import Runner

from . import settings

logger = logging.getLogger("cloud.backend.runner")

EXTRA_SYSTEM = (
    "你是 pagent，一名严谨的工程师。回答保持简洁、直接、准确；不要输出表情符号；"
    "不要使用寒暄、口号或不必要的解释。"
)


class UserRunner:
    """Holds a pagentv4 Runner per user, lazily created."""

    def __init__(self, user_id: str, publish_fn):
        self.user_id = user_id
        self.publish_fn = publish_fn
        self.runner: Runner | None = None
        self.turn_task: asyncio.Task | None = None

    async def ensure_runner(self) -> Runner:
        if self.runner is not None:
            return self.runner
        if not settings.LLM_API_KEY:
            raise RuntimeError("CLOUD_LLM_API_KEY 未配置")
        provider = DeepSeek(
            settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            apikey=settings.LLM_API_KEY,
        )
        thread_id = f"cloud-{self.user_id[:8]}-{datetime.now(UTC):%Y%m%d-%H%M%S}"
        self.runner = await Runner.create(
            thread_id,
            provider,
            root=settings.RUNTIME_ROOT,
            extra_system=EXTRA_SYSTEM,
            max_turns=24,
        )
        return self.runner

    def turn_active(self) -> bool:
        return self.turn_task is not None and not self.turn_task.done()

    async def run_turn(self, text: str) -> None:
        runner = await self.ensure_runner()
        if self.turn_active():
            logger.warning("user %s: turn already active, ignoring", self.user_id)
            return
        self.turn_task = asyncio.create_task(self._run(runner, text))

    async def _run(self, runner: Runner, text: str) -> None:
        try:
            async for event in runner.run(text, return_type="event"):
                line = encode_event_line(event)
                await self.publish_fn(line.rstrip("\n"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("turn failed for user %s", self.user_id)
            await self.publish_fn_error(str(exc))

    async def publish_fn_error(self, message: str) -> None:
        wire = json.dumps(
            {"jsonrpc": "2.0", "method": "Error", "params": {"message": message}},
            ensure_ascii=False,
        )
        await self.publish_fn(wire)

    def cancel(self) -> None:
        if self.runner and self.turn_active():
            self.runner.cancel_run()

    async def reset(self) -> None:
        if self.turn_active() and self.turn_task:
            self.turn_task.cancel()
            try:
                await self.turn_task
            except (asyncio.CancelledError, Exception):
                pass
        self.runner = None
        self.turn_task = None
