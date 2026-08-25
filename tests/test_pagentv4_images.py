"""上传图片落盘：data URL 解析与写入沙箱 uploads/ 目录。"""

from __future__ import annotations

import base64
import json
from types import SimpleNamespace

import pytest

from app import wire
from pagentv4 import ImageAttachment, ImageUrl, Message, Messages
from pagentv4.runtime.images import (
    ImageInput,
    attachment_data_url,
    decode_data_url,
    migrate_inline_images,
    persist_image_input,
    resolve_attachment_path,
    resolve_message_attachments,
    save_images_to_sandbox,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-body"
PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode("ascii")
MODEL_BYTES = b"\x89PNG\r\n\x1a\nscaled-model-body"
MODEL_DATA_URL = "data:image/png;base64," + base64.b64encode(MODEL_BYTES).decode(
    "ascii"
)


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


def test_persist_image_input_keeps_original_and_model_variants(tmp_path):
    thread = SimpleNamespace(root=tmp_path)

    attachment = persist_image_input(
        thread,
        ImageInput(original_url=PNG_DATA_URL, model_url=MODEL_DATA_URL),
    )

    assert isinstance(attachment, ImageAttachment)
    assert attachment.original_path != attachment.model_path
    assert (tmp_path / attachment.original_path).read_bytes() == PNG_BYTES
    assert (tmp_path / attachment.model_path).read_bytes() == MODEL_BYTES
    assert attachment_data_url(thread, attachment, original=True) == PNG_DATA_URL
    assert attachment_data_url(thread, attachment, original=False) == MODEL_DATA_URL


def test_persist_image_input_deduplicates_identical_variants(tmp_path):
    thread = SimpleNamespace(root=tmp_path)

    attachment = persist_image_input(
        thread,
        ImageInput(original_url=PNG_DATA_URL, model_url=PNG_DATA_URL),
    )

    assert isinstance(attachment, ImageAttachment)
    assert attachment.original_path == attachment.model_path
    assert len(list((tmp_path / "attachments").iterdir())) == 1


def test_attachment_path_cannot_escape_thread_attachment_root(tmp_path):
    thread = SimpleNamespace(root=tmp_path)

    with pytest.raises(ValueError, match="escapes attachment root"):
        resolve_attachment_path(thread, "../outside.png")


def test_resolve_message_attachments_uses_model_variant(tmp_path):
    thread = SimpleNamespace(root=tmp_path)
    attachment = persist_image_input(
        thread,
        ImageInput(original_url=PNG_DATA_URL, model_url=MODEL_DATA_URL),
    )
    assert isinstance(attachment, ImageAttachment)
    messages = Messages(
        data=[
            Message.user("inspect"),
            Message.user_image_attachment(attachment),
        ]
    )

    resolved = resolve_message_attachments(messages, thread)

    assert isinstance(messages.data[1].content, ImageAttachment)
    assert isinstance(resolved.data[1].content, ImageUrl)
    assert resolved.data[1].content.url == MODEL_DATA_URL
    assert resolved.to_openai()[0]["content"][1]["image_url"]["url"] == MODEL_DATA_URL


def test_history_replay_uses_original_variant(tmp_path):
    thread = SimpleNamespace(root=tmp_path)
    attachment = persist_image_input(
        thread,
        ImageInput(original_url=PNG_DATA_URL, model_url=MODEL_DATA_URL),
    )
    assert isinstance(attachment, ImageAttachment)
    messages = Messages(data=[Message.user_image_attachment(attachment)])

    items = wire.history_message_items(messages, thread)

    assert items == [{"kind": "image", "role": "user", "url": PNG_DATA_URL}]


def test_migrate_inline_images_rewrites_jsonl_reference(tmp_path):
    thread = SimpleNamespace(root=tmp_path)
    messages = Messages(data=[Message.user_image(PNG_DATA_URL)])

    assert migrate_inline_images(messages, thread) is True
    content = messages.data[0].content
    assert isinstance(content, ImageAttachment)

    path = tmp_path / "messages.jsonl"
    messages.save_to_jsonl(path)
    saved = json.loads(path.read_text().strip())
    assert saved["content"]["type"] == "image_attachment"
    assert "base64" not in path.read_text()
