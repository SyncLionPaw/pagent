"""HTTP 后端：与 wire 共享同一套命令处理核，只换传输壳。

对齐关系（一字不改命令/事件 JSON）：

- wire 的 stdin（收 JSON 命令）  → ``POST /command``（body 是同一个命令对象）
- wire 的 stdout（出事件流）      → ``GET /events``（SSE，每行事件一个 data 帧）

另挂 ``/api/*`` 宿主能力（项目树 / 产物预览等），以及可选的 React Web 静态资源，
形状对齐 desktop 的 ``DesktopApi``。

会话模型沿用 wire 的"单进程·单会话·单 runner·一次一轮"，正是 cloud
agent-in-the-pod 形态（一个 pod 服务一个会话）。server 跑在 uvicorn 的
asyncio loop，``inbound.permit/deny/cancel`` 与 ``run`` 同 loop，无跨线程 marshal。

依赖 fastapi / uvicorn，装 ``pagent[server]`` 才可用。
"""

import asyncio
import os
from pathlib import Path

from .config import ReplConfig
from .transport import FanoutSink, set_active_sink
from .wire import (
    clean_empty_threads,
    handle_command,
    log,
    parse_command,
    slash_commands_line,
)

AUTH_ENV = "PAGENT_SERVER_TOKEN"


class WireHttpSession:
    """承载单会话的 runner / state，串行化命令分派（对齐 wire 主循环的顺序处理）。"""

    def __init__(self, config: ReplConfig, sink: FanoutSink) -> None:
        self.config = config
        self.sink = sink
        self.runner = None
        self.state: dict = {"turn": None, "client_features": {}}
        self.had_user_turn = False
        self.project_path = (
            str(Path(config.project_path).expanduser()) if config.project_path else ""
        )
        self.yolo_mode = config.permission_auto()
        self._lock = asyncio.Lock()

    def effective_project_path(self) -> str:
        if self.project_path:
            return self.project_path
        from .web_host import default_project_path

        return str(default_project_path())

    async def dispatch(self, command: dict) -> None:
        """处理一条命令；同一时刻只处理一条（user 起后台 turn 后立即返回）。"""
        async with self._lock:
            # 记住前端传来的 project_path，供 /api 宿主接口使用。
            project = command.get("project_path")
            if isinstance(project, str) and project.strip():
                self.project_path = project.strip()
            prev_count = (
                len(self.runner.messages.data) if self.runner is not None else 0
            )
            self.runner = await handle_command(
                command, self.runner, self.config, self.state
            )
            if self.runner is not None and len(self.runner.messages.data) > prev_count:
                self.had_user_turn = True

    async def close(self) -> None:
        task = self.state.get("turn")
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self.runner is not None:
            thread_id = self.runner.thread.id
            await self.runner.close()
            clean_empty_threads(
                keep_thread_ids={thread_id} if self.had_user_turn else set()
            )


def check_auth(header_value: str | None) -> bool:
    """校验 Authorization: Bearer <token>。未设 PAGENT_SERVER_TOKEN 时放行。"""
    token = os.getenv(AUTH_ENV, "").strip()
    if not token:
        return True
    if not header_value:
        return False
    prefix = "Bearer "
    if not header_value.startswith(prefix):
        return False
    return header_value[len(prefix) :].strip() == token


def sse_frame(line: str) -> str:
    """把一行事件包成一个 SSE data 帧。"""
    return f"data: {line.rstrip()}\n\n"


async def event_stream(sink: FanoutSink):
    """一个 SSE 连接的事件生成器：先回放 slash 菜单，再转发 sink 广播直到哨兵。"""
    queue = sink.subscribe()
    try:
        # 新连接先回放 slash 菜单，对齐 wire 启动即下发的行为。
        yield sse_frame(slash_commands_line())
        while True:
            line = await queue.get()
            if line is None:
                break
            yield sse_frame(line)
    finally:
        sink.unsubscribe(queue)


def build_app(config: ReplConfig):
    """构造 FastAPI 应用。进程级把事件出口切到 FanoutSink，命令核复用 wire。"""
    from contextlib import asynccontextmanager

    from fastapi import Body, FastAPI, Header, HTTPException, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles

    from . import web_host

    sink = FanoutSink()
    set_active_sink(sink)
    session = WireHttpSession(config, sink)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        await session.close()
        sink.close()

    app = FastAPI(title="pagent http backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("PAGENT_CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def require_auth(authorization: str | None) -> None:
        if not check_auth(authorization):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/events")
    async def events(authorization: str | None = Header(default=None)):
        require_auth(authorization)
        return StreamingResponse(event_stream(sink), media_type="text/event-stream")

    @app.post("/command")
    async def command(
        request: Request, authorization: str | None = Header(default=None)
    ):
        require_auth(authorization)
        raw = await request.body()
        parsed = parse_command(raw.decode("utf-8"))
        if parsed is None:
            raise HTTPException(status_code=400, detail="invalid command")
        await session.dispatch(parsed)
        return {"ok": True}

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/api/app-info")
    async def api_app_info(authorization: str | None = Header(default=None)):
        require_auth(authorization)
        return web_host.app_info()

    @app.get("/api/runtime-state")
    async def api_runtime_state(authorization: str | None = Header(default=None)):
        require_auth(authorization)
        from pagentv4.paths import resolve_pagent_home

        project = session.effective_project_path()
        home_path = resolve_pagent_home()
        thread_id = None
        backend = None
        if session.runner is not None:
            thread_id = session.runner.thread.id
            backend = getattr(session.runner.thread.spec, "backend", None)
        return {
            "projectPath": project,
            "activeHomePath": str(home_path),
            "activeHomeScope": "user",
            "currentThreadId": thread_id,
            "sandboxBackend": backend,
            "sandboxAlive": None,
            "yoloMode": session.yolo_mode,
            "bridgeActive": True,
            "transport": "http",
            "status": "ready",
        }

    @app.post("/api/yolo")
    async def api_yolo(
        request: Request, authorization: str | None = Header(default=None)
    ):
        require_auth(authorization)
        body = await request.json()
        session.yolo_mode = bool(body.get("enabled"))
        return {"yoloMode": session.yolo_mode}

    @app.get("/api/settings")
    async def api_settings(authorization: str | None = Header(default=None)):
        require_auth(authorization)
        return web_host.read_settings()

    @app.get("/api/artifacts")
    async def api_artifacts(
        project_path: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)
        path = project_path or session.effective_project_path()
        return web_host.list_artifacts(path)

    @app.get("/api/artifacts/read")
    async def api_artifact_read(
        path: str = Query(...),
        project_path: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)
        root = project_path or session.effective_project_path()
        return web_host.read_artifact(root, path)

    @app.post("/api/artifacts/open")
    async def api_artifact_open(
        body: dict = Body(...),
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)
        path = body.get("path")
        if not isinstance(path, str) or not path.strip():
            raise HTTPException(status_code=400, detail="path required")
        project_path = body.get("projectPath")
        root = (
            project_path.strip()
            if isinstance(project_path, str) and project_path.strip()
            else session.effective_project_path()
        )
        ok = web_host.open_artifact(root, path.strip())
        if not ok:
            raise HTTPException(status_code=404, detail="artifact not found")
        return {"ok": True}

    @app.get("/api/project-files")
    async def api_project_files(
        project_path: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)
        path = project_path or session.effective_project_path()
        return web_host.list_project_files(path)

    @app.get("/api/project-tree")
    async def api_project_tree(
        project_path: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)
        path = project_path or session.effective_project_path()
        return web_host.list_project_tree(path)

    @app.get("/api/new-session-options")
    async def api_new_session_options(
        project_path: str | None = Query(default=None),
        authorization: str | None = Header(default=None),
    ):
        require_auth(authorization)
        path = project_path or session.effective_project_path()
        return web_host.new_session_options(path, config)

    @app.get("/api/thread-meta/{thread_id}")
    async def api_thread_meta(
        thread_id: str, authorization: str | None = Header(default=None)
    ):
        require_auth(authorization)
        try:
            return web_host.read_thread_meta(thread_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/project-path")
    async def api_set_project_path(
        request: Request, authorization: str | None = Header(default=None)
    ):
        require_auth(authorization)
        body = await request.json()
        path = body.get("projectPath")
        if not isinstance(path, str) or not path.strip():
            raise HTTPException(status_code=400, detail="projectPath required")
        resolved = web_host.resolve_project_path(path.strip())
        session.project_path = str(resolved)
        return {"projectPath": session.project_path}

    dist = web_host.resolve_web_dist()
    if dist is not None:
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/")
        async def spa_index():
            return FileResponse(dist / "index.html")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            # 不拦截 API / 事件 / 命令。
            if full_path.startswith(("api/", "events", "command", "assets/")):
                raise HTTPException(status_code=404)
            candidate = dist / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

        log(f"[http] serving web UI from {dist}")
    else:
        log("[http] web dist not found (build editors/web); API-only mode")

    return app


def run_http(config: ReplConfig, *, host: str = "127.0.0.1", port: int = 8848) -> int:
    """启动 uvicorn 跑 HTTP 后端。缺 fastapi/uvicorn 时给出安装提示。"""
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "HTTP 后端需要 fastapi/uvicorn：安装 `pip install 'pagent[server]'`"
        ) from exc

    if not os.getenv(AUTH_ENV, "").strip():
        log(f"[http] 未设 {AUTH_ENV}，接口不鉴权（仅建议本机/受信任内网）")

    app = build_app(config)
    log(f"[http] ready on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0
