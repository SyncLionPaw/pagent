"""上传图片落盘：data URL 解析与写入沙箱 uploads/ 目录。"""

from __future__ import annotations

import base64

import pytest

from pagentv4.runtime.images import decode_data_url, save_images_to_sandbox

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-body"
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode("ascii")


class FakeFiles:
    def __init__(self) -> None:
        self.written: list[tuple[str, bytes]] = []

    async def write(self, path: str, data: bytes) -> None:
        self.written.append((path, data))


class FakeSandbox:
    def __init__(self) -> None:
        self.files = FakeFiles()


def test_decode_data_url_png():
    result = decode_data_url(PNG_DATA_URL)
    assert result is not None
    mime, payload = result
    assert mime == "image/png"
    assert payload == PNG_BYTES


def test_decode_data_url_rejects_http_url():
    assert decode_data_url("https://example.com/a.png") is None


def test_decode_data_url_rejects_bad_base64():
    assert decode_data_url("data:image/png;base64,@@not-base64@@") is None


@pytest.mark.asyncio
async def test_save_images_writes_decoded_bytes():
    sandbox = FakeSandbox()
    saved = await save_images_to_sandbox(sandbox, [PNG_DATA_URL])
    assert len(saved) == 1
    assert saved[0].startswith("uploads/")
    assert saved[0].endswith(".png")
    path, data = sandbox.files.written[0]
    assert path == saved[0]
    assert data == PNG_BYTES


@pytest.mark.asyncio
async def test_save_images_skips_non_data_urls():
    sandbox = FakeSandbox()
    saved = await save_images_to_sandbox(sandbox, ["https://example.com/a.png"])
    assert saved == []
    assert sandbox.files.written == []


@pytest.mark.asyncio
async def test_save_images_no_sandbox_is_noop():
    saved = await save_images_to_sandbox(None, [PNG_DATA_URL])
    assert saved == []


@pytest.mark.asyncio
async def test_save_images_indexes_multiple():
    sandbox = FakeSandbox()
    jpg = "data:image/jpeg;base64," + base64.b64encode(b"jpeg-body").decode("ascii")
    saved = await save_images_to_sandbox(sandbox, [PNG_DATA_URL, jpg])
    assert len(saved) == 2
    assert saved[0].endswith("-0.png")
    assert saved[1].endswith("-1.jpg")
