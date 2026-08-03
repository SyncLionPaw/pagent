"""每用户、每 thread 的 pagentv4 Runner 管理。

对话消息不再落磁盘 JSONL：Runner 创建后把 ConversationStore 换成
PostgresConversationStore，引擎每次 checkpoint 直接写 thread_messages 表。thread.toml
与 workspaces 等沙箱脚手架仍在 RUNTIME_ROOT 下（那是沙箱需要的运行时目录，不是对话内容）。

一个 UserRunner 绑定一个 (user_id, thread_id)。切换会话时由 app 层重建。
"""

from __future__ import annotations

import asyncio
import json
import logging

from pagentv4.adapters.acp import encode_event_line
from pagentv4.core.provider import DeepSeek
from pagentv4.runtime import Runner

from . import settings
from .conversation_store import PostgresConversationStore

logger = logging.getLogger("cloud.backend.runner")

EXTRA_SYSTEM = (
    "你是 pagent，一名严谨的工程师。回答保持简洁、直接、准确；不要输出表情符号；"
    "不要使用寒暄、口号或不必要的解释。"
)


class UserRunner:
    """持有绑定到某个 thread 的 pagentv4 Runner，惰性创建。"""

    def __init__(self, user_id: str, thread_id: str, publish_fn):
        self.user_id = user_id
        self.thread_id = thread_id
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
        runner = await Runner.create(
            self.thread_id,
            provider,
            root=settings.RUNTIME_ROOT,
            extra_system=EXTRA_SYSTEM,
            max_turns=24,
        )
        # 换后端：对话消息以 Postgres 为单一事实源，覆盖引擎默认的 JSONL store，
        # 并用库里已有的历史重建内存消息（resume 后续跑同一会话）。
        store = PostgresConversationStore(self.thread_id, self.user_id)
        runner.store = store
        runner.messages = store.load(runner.conversation_id or "")
        self.runner = runner
        return runner

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
            await self.publish_error(str(exc))

    async def publish_error(self, message: str) -> None:
        wire = json.dumps(
            {"jsonrpc": "2.0", "method": "Error", "params": {"message": message}},
            ensure_ascii=False,
        )
        await self.publish_fn(wire)

    def cancel(self) -> None:
        if self.runner and self.turn_active():
            self.runner.cancel_run()

    async def close(self) -> None:
        if self.turn_active() and self.turn_task:
            self.turn_task.cancel()
            try:
                await self.turn_task
            except (asyncio.CancelledError, Exception):
                pass
        if self.runner is not None:
            await self.runner.close()
        self.runner = None
        self.turn_task = None
