"""上传图片落盘：把 data URL 图片本体在沙箱里存一份，方便工具处理与事后回看。

图片本体仍留在消息里供视觉模型使用；这里额外把 base64 data URL 解码后写进沙箱的
``uploads/`` 目录，作为可被文件工具访问的副本。远程 http 图片不是上传内容，跳过。
"""

from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime

# data:image/png;base64,<payload>
_DATA_URL_RE = re.compile(
    r"^data:(?P<mime>image/[\w.+-]+);base64,(?P<payload>.+)$", re.DOTALL
)

_MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}


def decode_data_url(url: str) -> tuple[str, bytes] | None:
    """解析 base64 data URL，返回 (mime, 原始字节)；非 data URL 返回 None。"""
    match = _DATA_URL_RE.match(url.strip())
    if match is None:
        return None
    try:
        payload = base64.b64decode(match.group("payload"), validate=True)
    except (binascii.Error, ValueError):
        return None
    return match.group("mime"), payload


async def save_images_to_sandbox(
    sandbox, images: list[str], *, subdir: str = "uploads"
) -> list[str]:
    """把 data URL 图片写进沙箱 ``subdir`` 目录，返回保存的虚拟路径列表。

    沙箱为空（如纯内存 VanillaRunner）或图片非 data URL 时直接跳过。
    """
    if sandbox is None:
        return []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    saved: list[str] = []
    for index, url in enumerate(images):
        decoded = decode_data_url(url)
        if decoded is None:
            continue
        mime, payload = decoded
        ext = _MIME_EXT.get(mime, "bin")
        path = f"{subdir}/{stamp}-{index}.{ext}"
        await sandbox.files.write(path, payload)
        saved.append(path)
    return saved
