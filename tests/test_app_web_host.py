"""Web host API：项目树、产物、新建会话选项。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import http_server, web_host
from app.config import ReplConfig
from app.transport import StdoutSink, set_active_sink


def test_list_project_tree_and_files(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hi\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("x", encoding="utf-8")

    tree = web_host.list_project_tree(str(tmp_path))
    labels = {node["label"] for node in tree}
    assert "src" in labels
    assert "README.md" in labels
    assert "node_modules" not in labels

    files = web_host.list_project_files(str(tmp_path))
    assert "README.md" in files
    assert "src/main.py" in files
    assert all("node_modules" not in path for path in files)


def test_artifacts_list_and_read(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "note.md").write_text("# hello\n", encoding="utf-8")
    (artifacts / "data.bin").write_bytes(b"\x00\x01\x02")

    listed = web_host.list_artifacts(str(tmp_path))
    names = {item["name"] for item in listed}
    assert names == {"note.md", "data.bin"}

    md = web_host.read_artifact(str(tmp_path), str(artifacts / "note.md"))
    assert md["kind"] == "markdown"
    assert "# hello" in (md.get("text") or "")

    binary = web_host.read_artifact(str(tmp_path), "data.bin")
    assert binary["kind"] == "binary"


def test_api_host_routes(monkeypatch, tmp_path: Path):
    monkeypatch.delenv(http_server.AUTH_ENV, raising=False)
    (tmp_path / "hello.txt").write_text("x\n", encoding="utf-8")
    app = http_server.build_app(ReplConfig(project_path=str(tmp_path)))
    client = TestClient(app)

    assert client.get("/api/health").json() == {"ok": True}
    info = client.get("/api/app-info").json()
    assert info["name"] == "pagent Web"

    state = client.get("/api/runtime-state").json()
    assert state["transport"] == "http"
    assert state["projectPath"] == str(tmp_path.resolve())

    tree = client.get("/api/project-tree").json()
    assert any(node["label"] == "hello.txt" for node in tree)

    options = client.get("/api/new-session-options").json()
    assert "local" in options["availableBackends"]
    assert options["projectPath"] == str(tmp_path.resolve())

    yolo = client.post("/api/yolo", json={"enabled": True}).json()
    assert yolo["yoloMode"] is True

    set_active_sink(StdoutSink())


def test_api_requires_auth(monkeypatch):
    monkeypatch.setenv(http_server.AUTH_ENV, "secret")
    app = http_server.build_app(ReplConfig())
    client = TestClient(app)
    assert client.get("/api/app-info").status_code == 401
    ok = client.get("/api/app-info", headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 200
    set_active_sink(StdoutSink())
