from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import db, settings, storage, threads
from .auth import create_jwt, verify_jwt
from .conversation_store import PostgresConversationStore
from .history import history_message_items
from .runner import UserRunner

logger = logging.getLogger("cloud.backend")

DEFAULT_PROJECT_PATH = "/cloud/demo"
DEFAULT_IMAGE = "pagent:latest"
# 首条用户消息压成一行标题的最大字符数，超出截断加省略号。
TITLE_MAX_CHARS = 40


def make_title(text: str) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= TITLE_MAX_CHARS:
        return one_line
    return one_line[:TITLE_MAX_CHARS] + "…"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        result = db.bootstrap()
        logger.info("database bootstrap: %s", result)
    except Exception:
        logger.exception("database bootstrap skipped / failed")
    try:
        storage.ensure_bucket()
        logger.info("object storage bucket ready: %s", settings.S3_BUCKET)
    except Exception:
        logger.exception("object storage bootstrap skipped / failed")
    yield


app = FastAPI(title="pagent cloud backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


user_state_by_id: dict[str, dict[str, Any]] = {}
subscriber_queues_by_user: dict[str, list[asyncio.Queue[str | None]]] = defaultdict(
    list
)
# 每 (user_id, thread_id) 一个 runner；切换会话时按需新建，旧的关闭。
user_runners: dict[tuple[str, str], UserRunner] = {}


def read_current_user(authorization: str | None) -> dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization[len("Bearer ") :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        claims = verify_jwt(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {
        "id": claims["sub"],
        "username": claims["username"],
        "displayName": claims["username"],
    }


def state_for(user_id: str) -> dict[str, Any]:
    if user_id not in user_state_by_id:
        user_state_by_id[user_id] = {
            "projectPath": DEFAULT_PROJECT_PATH,
            "yoloMode": False,
            "currentThreadId": None,
        }
    return user_state_by_id[user_id]


def wire_message(method: str, params: dict[str, Any]) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params},
        ensure_ascii=False,
    )


def sse_frame(line: str) -> str:
    return f"data: {line}\n\n"


async def publish_event(user_id: str, method: str, params: dict[str, Any]) -> None:
    message = wire_message(method, params)
    for queue in list(subscriber_queues_by_user[user_id]):
        await queue.put(message)


async def publish_event_raw(user_id: str, wire_line: str) -> None:
    for queue in list(subscriber_queues_by_user[user_id]):
        await queue.put(wire_line)


def thread_list_payload(user_id: str) -> dict[str, Any]:
    return {"threads": threads.list_threads(user_id)}


def history_replay_payload(
    user_id: str, thread: dict[str, Any] | None, project_path: str
) -> dict[str, Any]:
    """当前会话的回放载荷：空会话返回空数组（前端清屏）。"""
    if thread is None:
        return {
            "thread_id": "",
            "title": "",
            "project_path": project_path,
            "messages": [],
        }
    store = PostgresConversationStore(thread["id"], user_id)
    messages = store.load("")
    return {
        "thread_id": thread["id"],
        "title": thread["title"],
        "project_path": thread["project_path"] or project_path,
        "messages": history_message_items(messages),
    }


async def get_user_runner(user_id: str, thread_id: str, publish_fn) -> UserRunner:
    """取该用户在指定 thread 上的 runner；切到别的 thread 时关掉旧的，一人一活跃会话。"""
    for (owner, tid), runner in list(user_runners.items()):
        if owner == user_id and tid != thread_id:
            await runner.close()
            user_runners.pop((owner, tid), None)
    key = (user_id, thread_id)
    if key not in user_runners:
        user_runners[key] = UserRunner(user_id, thread_id, publish_fn)
    return user_runners[key]


def sandbox_status_payload() -> dict[str, Any]:
    return {"thread_id": "", "backend": "", "alive": False, "workdir": ""}


def environment_payload() -> dict[str, Any]:
    return {
        "uvInstalled": True,
        "uvPath": "uv",
        "pagentInstalled": True,
        "pagentPath": "pagent",
        "apiKeyConfigured": True,
        "dockerInstalled": False,
        "podmanInstalled": False,
        "containerRuntime": None,
        "sandboxImage": DEFAULT_IMAGE,
        "sandboxImageExists": False,
        "configPath": "/cloud/config/pagent.toml",
        "dataHomePath": "/cloud/data",
        "dataHomeLabel": "cloud",
    }


def config_snapshot_payload() -> dict[str, Any]:
    return {
        "provider": {
            "api_key_configured": True,
            "model": "deepseek-v4-flash",
            "base_url": "",
        }
    }


async def event_stream(user_id: str):
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    subscriber_queues_by_user[user_id].append(queue)
    state = state_for(user_id)
    try:
        yield sse_frame(
            wire_message(
                "SlashCommands",
                {
                    "commands": [
                        {"name": "/help", "description": "查看帮助"},
                        {"name": "/clear", "description": "清空当前对话"},
                    ]
                },
            )
        )
        yield sse_frame(wire_message("ThreadList", thread_list_payload(user_id)))
        current_id = state["currentThreadId"]
        thread = threads.get_thread(current_id, user_id) if current_id else None
        yield sse_frame(
            wire_message(
                "HistoryReplay",
                history_replay_payload(user_id, thread, state["projectPath"]),
            )
        )
        while True:
            line = await queue.get()
            if line is None:
                break
            yield sse_frame(line)
    finally:
        subscribers = subscriber_queues_by_user[user_id]
        if queue in subscribers:
            subscribers.remove(queue)


async def run_user_turn(user_id: str, state: dict[str, Any], text: str) -> None:
    """跑一轮对话：无当前 thread 就先建一条（首条消息定标题），再驱动 runner。

    消息落库由 PostgresConversationStore 在引擎 checkpoint 时完成；这里只负责
    thread 登记、标题、状态与列表刷新。
    """
    thread_id = state["currentThreadId"]
    is_new = thread_id is None
    if is_new:
        thread_id = threads.new_thread_id()
        threads.create_thread(
            thread_id=thread_id,
            owner_user_id=user_id,
            title=make_title(text),
            project_path=state["projectPath"],
            sandbox_backend="none",
            model=settings.LLM_MODEL,
        )
        state["currentThreadId"] = thread_id
        await publish_event(
            user_id,
            "CurrentThread",
            {
                "thread_id": thread_id,
                "title": make_title(text),
                "project_path": state["projectPath"],
            },
        )
    else:
        threads.set_title_if_empty(thread_id, user_id, make_title(text))

    async def publish_wire(wire_line: str):
        await publish_event_raw(user_id, wire_line)

    runner = await get_user_runner(user_id, thread_id, publish_wire)
    await runner.run_turn(text)
    if is_new:
        await publish_event(user_id, "ThreadList", thread_list_payload(user_id))


async def handle_command_for_user(
    user: dict[str, str], command: dict[str, Any]
) -> None:
    user_id = user["id"]
    state = state_for(user_id)
    cmd = str(command.get("cmd") or "")

    project_path = command.get("project_path")
    if isinstance(project_path, str) and project_path.strip():
        state["projectPath"] = project_path.strip()

    if cmd == "client_features":
        return

    if cmd == "commands":
        await publish_event(
            user_id,
            "SlashCommands",
            {
                "commands": [
                    {"name": "/help", "description": "查看帮助"},
                    {"name": "/clear", "description": "清空当前对话"},
                ]
            },
        )
        return

    if cmd == "list_threads":
        await publish_event(user_id, "ThreadList", thread_list_payload(user_id))
        return

    if cmd == "environment_check":
        await publish_event(user_id, "EnvironmentCheck", environment_payload())
        return

    if cmd == "get_config":
        await publish_event(user_id, "ConfigSnapshot", config_snapshot_payload())
        return

    if cmd == "skills":
        await publish_event(user_id, "Skills", {"skills": []})
        return

    if cmd == "sandbox_status":
        await publish_event(user_id, "SandboxStatus", sandbox_status_payload())
        return

    if cmd == "sandbox_tree":
        await publish_event(
            user_id,
            "SandboxTree",
            {"thread_id": "", "workdir": "", "nodes": []},
        )
        return

    if cmd == "reset":
        # 新建会话：清当前 thread 指向，前端清屏；真正的 thread 记录等首条用户消息落。
        state["currentThreadId"] = None
        await publish_event(
            user_id,
            "HistoryReplay",
            history_replay_payload(user_id, None, state["projectPath"]),
        )
        await publish_event(user_id, "ThreadList", thread_list_payload(user_id))
        return

    if cmd == "resume":
        thread_id = str(command.get("thread_id") or "")
        thread = threads.get_thread(thread_id, user_id) if thread_id else None
        if thread is None:
            await publish_event(user_id, "Error", {"message": "会话不存在或无权访问"})
            return
        state["currentThreadId"] = thread_id
        await publish_event(
            user_id,
            "HistoryReplay",
            history_replay_payload(user_id, thread, state["projectPath"]),
        )
        return

    if cmd == "delete_thread":
        thread_id = str(command.get("thread_id") or "")
        if thread_id:
            key = (user_id, thread_id)
            if key in user_runners:
                await user_runners.pop(key).close()
            threads.soft_delete(thread_id, user_id)
            if state["currentThreadId"] == thread_id:
                state["currentThreadId"] = None
                await publish_event(
                    user_id,
                    "HistoryReplay",
                    history_replay_payload(user_id, None, state["projectPath"]),
                )
        await publish_event(user_id, "ThreadList", thread_list_payload(user_id))
        return

    if cmd == "user":
        text = str(command.get("text") or "")
        if not text.strip():
            return
        await run_user_turn(user_id, state, text)
        return

    if cmd in {"cancel", "permit", "deny", "set_provider"}:
        if cmd == "cancel":
            current_id = state["currentThreadId"]
            runner = user_runners.get((user_id, current_id)) if current_id else None
            if runner is not None:
                runner.cancel()
        return

    await publish_event(
        user_id,
        "Error",
        {"message": f"暂不支持的命令：{cmd or 'unknown'}"},
    )


@app.get("/api/health")
def health() -> dict[str, Any]:
    db_status = db.ping()
    storage_status = storage.ping()
    ready = bool(db_status.get("ok") and storage_status.get("ok"))
    return {
        "ok": True,
        "ready": ready,
        "db": db_status,
        "storage": storage_status,
    }


@app.get("/api/ready")
def ready() -> dict[str, Any]:
    payload = health()
    if not payload["ready"]:
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.post("/api/auth/login")
def login(body: LoginRequest) -> dict[str, Any]:
    if (
        not settings.DEMO_MODE
        or body.username != settings.DEMO_USERNAME
        or body.password != settings.DEMO_PASSWORD
    ):
        raise HTTPException(status_code=401, detail="invalid username or password")
    user = {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "username": settings.DEMO_USERNAME,
        "displayName": settings.DEMO_USERNAME,
    }
    token = create_jwt(sub=user["id"], username=user["username"])
    return {"token": token, "user": user}


@app.get("/api/auth/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    return {"user": read_current_user(authorization)}


@app.get("/api/app-info")
def app_info(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = read_current_user(authorization)
    return {
        "name": "pagent Cloud",
        "version": "0.1.0",
        "platform": "cloud",
        "userName": user["username"],
    }


@app.get("/api/runtime-state")
def runtime_state(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = read_current_user(authorization)
    state = state_for(user["id"])
    return {
        "projectPath": state["projectPath"],
        "activeHomePath": "/cloud/data",
        "activeHomeScope": "user",
        "currentThreadId": state["currentThreadId"],
        "sandboxBackend": None,
        "sandboxAlive": None,
        "yoloMode": state["yoloMode"],
        "bridgeActive": True,
        "transport": "http",
        "status": "ready",
    }


@app.get("/api/settings")
def get_settings(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    read_current_user(authorization)
    return {
        "path": "/cloud/config/pagent.toml",
        "exists": False,
        "content": "",
    }


@app.get("/api/artifacts")
def artifacts(
    authorization: str | None = Header(default=None),
    project_path: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    read_current_user(authorization)
    return []


@app.get("/api/artifacts/read")
def read_artifact(
    authorization: str | None = Header(default=None),
    path: str = Query(...),
    project_path: str | None = Query(default=None),
) -> dict[str, Any]:
    read_current_user(authorization)
    return {
        "name": path.split("/")[-1],
        "path": path,
        "size": 0,
        "kind": "binary",
        "reason": "cloud demo 里还没有 artifact 内容",
    }


@app.post("/api/artifacts/open")
def open_artifact(
    authorization: str | None = Header(default=None),
    body: dict[str, Any] = Body(...),
) -> dict[str, bool]:
    read_current_user(authorization)
    raise HTTPException(status_code=404, detail="artifact not found")


@app.get("/api/project-files")
def project_files(
    authorization: str | None = Header(default=None),
    project_path: str | None = Query(default=None),
) -> list[str]:
    read_current_user(authorization)
    return []


@app.get("/api/project-tree")
def project_tree(
    authorization: str | None = Header(default=None),
    project_path: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    read_current_user(authorization)
    return []


@app.get("/api/new-session-options")
def new_session_options(
    authorization: str | None = Header(default=None),
    project_path: str | None = Query(default=None),
) -> dict[str, Any]:
    user = read_current_user(authorization)
    state = state_for(user["id"])
    return {
        "projectPath": project_path or state["projectPath"],
        "availableBackends": ["local"],
        "sshHosts": [],
        "defaultImage": DEFAULT_IMAGE,
        "availableImages": [],
    }


@app.get("/api/thread-meta/{thread_id}")
def thread_meta(
    thread_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = read_current_user(authorization)
    thread = threads.get_thread(thread_id, user["id"])
    if thread is None:
        raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")
    thread_path = Path(settings.RUNTIME_ROOT) / thread_id
    return {
        "id": thread["id"],
        "title": thread["title"],
        "createdAt": thread["created_at"] or "",
        "updatedAt": thread["updated_at"] or "",
        "messageCount": thread["message_count"],
        "threadPath": str(thread_path),
        "metainfo": thread,
    }


@app.post("/api/yolo")
def set_yolo(
    authorization: str | None = Header(default=None),
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    user = read_current_user(authorization)
    state = state_for(user["id"])
    state["yoloMode"] = bool(body.get("enabled"))
    return {"yoloMode": state["yoloMode"]}


@app.post("/api/project-path")
def set_project_path(
    authorization: str | None = Header(default=None),
    body: dict[str, Any] = Body(...),
) -> dict[str, str]:
    user = read_current_user(authorization)
    project_path = body.get("projectPath")
    if not isinstance(project_path, str) or not project_path.strip():
        raise HTTPException(status_code=400, detail="projectPath required")
    state = state_for(user["id"])
    state["projectPath"] = project_path.strip()
    return {"projectPath": state["projectPath"]}


@app.get("/events")
def events(authorization: str | None = Header(default=None)) -> StreamingResponse:
    user = read_current_user(authorization)
    return StreamingResponse(event_stream(user["id"]), media_type="text/event-stream")


@app.post("/command")
async def command(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, bool]:
    user = read_current_user(authorization)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="invalid command")
    await handle_command_for_user(user, body)
    return {"ok": True}
