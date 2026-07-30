from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth import create_jwt, verify_jwt

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123"
DEFAULT_PROJECT_PATH = "/cloud/demo"
DEFAULT_IMAGE = "pagent:latest"

app = FastAPI(title="pagent cloud backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


user_state_by_id: dict[str, dict[str, Any]] = {
    "user-admin": {
        "projectPath": DEFAULT_PROJECT_PATH,
        "yoloMode": False,
        "threads": [],
    }
}
subscriber_queues_by_user: dict[str, list[asyncio.Queue[str | None]]] = defaultdict(
    list
)


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
            "threads": [],
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


def thread_list_payload(user_id: str) -> dict[str, Any]:
    state = state_for(user_id)
    return {"threads": state["threads"]}


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
        yield sse_frame(
            wire_message(
                "HistoryReplay",
                {
                    "thread_id": "",
                    "title": "",
                    "project_path": state["projectPath"],
                    "messages": [],
                },
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
        await publish_event(
            user_id,
            "HistoryReplay",
            {
                "thread_id": "",
                "title": "",
                "project_path": state["projectPath"],
                "messages": [],
            },
        )
        await publish_event(user_id, "ThreadList", thread_list_payload(user_id))
        return

    if cmd == "resume":
        await publish_event(
            user_id,
            "Error",
            {"message": "cloud demo 暂时还没有可恢复的 thread"},
        )
        return

    if cmd == "delete_thread":
        await publish_event(user_id, "ThreadList", thread_list_payload(user_id))
        return

    if cmd == "user":
        text = str(command.get("text") or "")
        await publish_event(user_id, "RunBegin", {"user_input": text})
        await publish_event(
            user_id,
            "Error",
            {
                "message": "cloud demo backend 还没接入真实 agent，只先把 web 工作台挂起来"
            },
        )
        return

    if cmd in {"cancel", "permit", "deny", "set_provider"}:
        return

    await publish_event(
        user_id,
        "Error",
        {"message": f"暂不支持的命令：{cmd or 'unknown'}"},
    )


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/api/auth/login")
def login(body: LoginRequest) -> dict[str, Any]:
    if body.username != ADMIN_USERNAME or body.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="invalid username or password")
    user = {
        "id": "user-admin",
        "username": ADMIN_USERNAME,
        "displayName": "admin",
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
        "currentThreadId": None,
        "sandboxBackend": None,
        "sandboxAlive": None,
        "yoloMode": state["yoloMode"],
        "bridgeActive": True,
        "transport": "http",
        "status": "ready",
    }


@app.get("/api/settings")
def settings(authorization: str | None = Header(default=None)) -> dict[str, Any]:
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
    read_current_user(authorization)
    raise HTTPException(status_code=404, detail=f"thread not found: {thread_id}")


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
