"""Web 宿主侧能力：项目树、产物预览、新建会话选项等。

浏览器没有 Electron 主进程的本机 FS/对话框，这些由 ``pagent --http`` 代为执行，
形状对齐 desktop 的 ``DesktopApi``（见 editors/desktop/src/shared/protocol.ts）。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
from pathlib import Path

from pagentv4.paths import resolve_pagent_home

from .config import ReplConfig, load_config
from .environment import detect_container_runtime

PROJECT_FILE_IGNORE = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "__pycache__",
        ".DS_Store",
        "dist",
        "build",
        ".idea",
        ".vscode",
    }
)
PROJECT_FILE_LIMIT = 2000

ARTIFACT_TEXT_LIMIT = 512 * 1024
ARTIFACT_IMAGE_LIMIT = 8 * 1024 * 1024
ARTIFACT_HTML_LIMIT = 4 * 1024 * 1024
ARTIFACT_PDF_LIMIT = 32 * 1024 * 1024

ARTIFACT_LANGUAGES = {
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".sh": "bash",
    ".rb": "ruby",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".sql": "sql",
}

ARTIFACT_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
}

ARTIFACT_TEXT_EXT = frozenset(
    {".txt", ".log", ".csv", ".tsv", ".env", ".ini", ".cfg", ".conf"}
)

DEFAULT_SANDBOX_IMAGE = "pagent:latest"


def default_project_path() -> Path:
    return resolve_pagent_home() / "default"


def resolve_project_path(raw: str | None) -> Path:
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return default_project_path().resolve()


def app_info() -> dict:
    home = Path.home()
    return {
        "name": "pagent Web",
        "version": "0.7.20",
        "platform": os.name,
        "userName": home.name or "user",
    }


def read_settings() -> dict:
    path = resolve_pagent_home() / "pagent.toml"
    if not path.is_file():
        return {"path": str(path), "exists": False, "content": ""}
    return {
        "path": str(path),
        "exists": True,
        "content": path.read_text(encoding="utf-8"),
    }


def list_artifacts(project_path: str | None) -> list[dict]:
    root = resolve_project_path(project_path) / "artifacts"
    if not root.is_dir():
        return []
    items: list[dict] = []
    for entry in root.iterdir():
        if not entry.is_file():
            continue
        stat = entry.stat()
        items.append(
            {
                "id": entry.name,
                "name": entry.name,
                "path": str(entry),
                "size": stat.st_size,
                "mtimeMs": stat.st_mtime * 1000,
            }
        )
    items.sort(key=lambda item: item["mtimeMs"], reverse=True)
    return items


def _resolve_artifact(project_path: str | None, file_path: str) -> Path | None:
    root = (resolve_project_path(project_path) / "artifacts").resolve()
    target = Path(file_path).expanduser().resolve()
    try:
        target.relative_to(root)
    except ValueError:
        # 也允许只传文件名
        by_name = root / Path(file_path).name
        if by_name.is_file():
            return by_name
        return None
    return target if target.is_file() else None


def read_artifact(project_path: str | None, file_path: str) -> dict:
    name = Path(file_path).name
    target = _resolve_artifact(project_path, file_path)
    if target is None:
        return {
            "name": name,
            "path": file_path,
            "size": 0,
            "kind": "binary",
            "reason": "文件不存在",
        }
    size = target.stat().st_size
    ext = target.suffix.lower()
    base = {"name": target.name, "path": str(target), "size": size}

    image_mime = ARTIFACT_IMAGE_MIME.get(ext)
    if image_mime:
        if size > ARTIFACT_IMAGE_LIMIT:
            return {**base, "kind": "binary", "reason": "图片过大，无法内联预览"}
        data = base64.b64encode(target.read_bytes()).decode("ascii")
        return {**base, "kind": "image", "dataUrl": f"data:{image_mime};base64,{data}"}

    if ext == ".pdf":
        if size > ARTIFACT_PDF_LIMIT:
            return {**base, "kind": "binary", "reason": "PDF 过大，无法内联预览"}
        data = base64.b64encode(target.read_bytes()).decode("ascii")
        return {
            **base,
            "kind": "pdf",
            "dataUrl": f"data:application/pdf;base64,{data}",
        }

    if ext in {".html", ".htm"}:
        if size > ARTIFACT_HTML_LIMIT:
            return {**base, "kind": "binary", "reason": "HTML 过大，无法内联预览"}
        data = base64.b64encode(target.read_bytes()).decode("ascii")
        return {**base, "kind": "html", "dataUrl": f"data:text/html;base64,{data}"}

    raw = target.read_bytes()[:ARTIFACT_TEXT_LIMIT]
    known = ext in ARTIFACT_LANGUAGES or ext in ARTIFACT_TEXT_EXT
    if not known and b"\x00" in raw:
        return {**base, "kind": "binary", "reason": "二进制文件，无法内联预览"}
    text = raw.decode("utf-8", errors="replace")
    truncated = size > ARTIFACT_TEXT_LIMIT
    if ext in {".md", ".markdown"}:
        return {**base, "kind": "markdown", "text": text, "truncated": truncated}
    return {
        **base,
        "kind": "text",
        "language": ARTIFACT_LANGUAGES.get(ext),
        "text": text,
        "truncated": truncated,
    }


def open_artifact(project_path: str | None, file_path: str) -> bool:
    target = _resolve_artifact(project_path, file_path)
    if target is None:
        return False

    if os.name == "posix" and shutil.which("open"):
        subprocess.run(["open", "-R", str(target)], check=False)
        return True

    if os.name == "nt":
        subprocess.run(["explorer", "/select,", str(target)], check=False)
        return True

    opener = shutil.which("xdg-open")
    if opener:
        subprocess.run([opener, str(target.parent)], check=False)
        return True

    return False


def list_project_files(project_path: str | None) -> list[str]:
    root = resolve_project_path(project_path)
    if not root.is_dir():
        return []
    results: list[str] = []

    def walk(directory: Path) -> None:
        if len(results) >= PROJECT_FILE_LIMIT:
            return
        try:
            entries = sorted(
                directory.iterdir(), key=lambda p: (not p.is_dir(), p.name)
            )
        except OSError:
            return
        for entry in entries:
            if len(results) >= PROJECT_FILE_LIMIT:
                return
            if entry.name.startswith(".") and entry.name != ".pagent":
                continue
            if entry.name in PROJECT_FILE_IGNORE:
                continue
            if entry.is_dir():
                walk(entry)
            elif entry.is_file():
                results.append(str(entry.relative_to(root)))

    walk(root)
    results.sort()
    return results


def list_project_tree(project_path: str | None) -> list[dict]:
    root = resolve_project_path(project_path)
    return _tree_nodes(root)


def _tree_nodes(directory: Path, prefix: str = "") -> list[dict]:
    if not directory.is_dir():
        return []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    entries.sort(key=lambda p: (not p.is_dir(), p.name.lower()))
    nodes: list[dict] = []
    for entry in entries:
        if entry.name.startswith(".") and entry.name != ".pagent":
            continue
        if entry.name in PROJECT_FILE_IGNORE:
            continue
        node_id = f"{prefix}/{entry.name}" if prefix else entry.name
        if entry.is_dir():
            children = _tree_nodes(entry, node_id)
            nodes.append(
                {
                    "id": node_id,
                    "label": entry.name,
                    "kind": "dir",
                    "count": len(children),
                    "children": children,
                }
            )
        elif entry.is_file():
            nodes.append({"id": node_id, "label": entry.name, "kind": "file"})
    return nodes


def read_ssh_hosts(config_path: Path | None = None) -> list[str]:
    path = config_path or (Path.home() / ".ssh" / "config")
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    hosts: list[str] = []
    for line in text.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        if not trimmed.lower().startswith("host "):
            continue
        for token in trimmed[5:].strip().split():
            if "*" in token or "?" in token:
                continue
            hosts.append(token)
    return hosts


def list_sandbox_images(default_image: str) -> list[str]:
    runtime = detect_container_runtime()
    images = [default_image]
    if not runtime:
        return images
    try:
        out = subprocess.check_output(
            [runtime, "images", "--format", "{{.Repository}}:{{.Tag}}"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return images
    found = []
    for line in out.splitlines():
        name = line.strip()
        if not name or name.endswith(":<none>"):
            continue
        if "pagent" in name.lower() or name == default_image:
            found.append(name)
    for name in found:
        if name not in images:
            images.append(name)
    return images


def new_session_options(
    project_path: str | None, config: ReplConfig | None = None
) -> dict:
    cfg = config or load_config()
    default_image = (
        cfg.image or DEFAULT_SANDBOX_IMAGE
    ).strip() or DEFAULT_SANDBOX_IMAGE
    backends = ["local"]
    if detect_container_runtime():
        backends.append("container")
    backends.append("ssh")
    project = resolve_project_path(project_path)
    return {
        "projectPath": str(project),
        "availableBackends": backends,
        "sshHosts": read_ssh_hosts(),
        "defaultImage": default_image,
        "availableImages": list_sandbox_images(default_image),
    }


def guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def web_dist_candidates() -> list[Path]:
    """查找 React 构建产物目录。"""
    env = os.getenv("PAGENT_WEB_DIST", "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser())
    here = Path(__file__).resolve()
    # src/app/web_host.py → repo editors/web/dist
    candidates.append(here.parents[2] / "editors" / "web" / "dist")
    candidates.append(Path.cwd() / "editors" / "web" / "dist")
    return candidates


def resolve_web_dist() -> Path | None:
    for path in web_dist_candidates():
        if (path / "index.html").is_file():
            return path.resolve()
    return None


def which_cli(name: str) -> str | None:
    return shutil.which(name)


_THREAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def read_thread_meta(thread_id: str) -> dict:
    if not _THREAD_ID_RE.match(thread_id):
        raise ValueError("invalid thread id")
    thread_path = resolve_pagent_home() / "threads" / thread_id
    meta_path = thread_path / "metainfo.json"
    meta: dict = {}
    if meta_path.is_file():
        try:
            value = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                meta = value
        except (OSError, json.JSONDecodeError):
            meta = {}
    message_count = meta.get("message_count")
    return {
        "id": thread_id,
        "title": meta.get("title") if isinstance(meta.get("title"), str) else "",
        "createdAt": meta.get("created_at")
        if isinstance(meta.get("created_at"), str)
        else "",
        "updatedAt": meta.get("updated_at")
        if isinstance(meta.get("updated_at"), str)
        else "",
        "messageCount": message_count if isinstance(message_count, int) else None,
        "threadPath": str(thread_path),
        "metainfo": meta,
    }
