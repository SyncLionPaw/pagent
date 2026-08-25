"""Thread image attachments and OpenAI data URL materialization."""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from ..core.message import ImageAttachment, ImageUrl, Message, Messages

ATTACHMENTS_DIRNAME = "attachments"

# data:image/png;base64,<payload>
DATA_URL_RE = re.compile(
    r"^data:(?P<mime>image/[\w.+-]+);base64,(?P<payload>.+)$", re.DOTALL
)

MIME_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}


@dataclass(frozen=True)
class ImageInput:
    """Original image for UI replay plus the derived image sent to the model."""

    original_url: str
    model_url: str


def decode_data_url(url: str) -> tuple[str, bytes] | None:
    """Parse a base64 image data URL into its MIME and bytes."""
    match = DATA_URL_RE.match(url.strip())
    if match is None:
        return None
    try:
        payload = base64.b64decode(match.group("payload"), validate=True)
    except (binascii.Error, ValueError):
        return None
    return match.group("mime"), payload


def encode_data_url(mime: str, payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def attachment_root(thread) -> Path:
    return thread.root / ATTACHMENTS_DIRNAME


def resolve_attachment_path(thread, relative_path: str) -> Path:
    root = attachment_root(thread).resolve()
    path = (thread.root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"image attachment escapes attachment root: {relative_path!r}")
    return path


def save_attachment_variant(thread, mime: str, payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    extension = MIME_EXTENSIONS.get(mime, "bin")
    relative_path = f"{ATTACHMENTS_DIRNAME}/{digest}.{extension}"
    path = resolve_attachment_path(thread, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(payload)
    return relative_path


def persist_image_input(thread, image: str | ImageInput) -> ImageUrl | ImageAttachment:
    if isinstance(image, str):
        decoded = decode_data_url(image)
        if decoded is None:
            return ImageUrl(type="image_url", url=image)
        original_mime, original_payload = decoded
        original_path = save_attachment_variant(thread, original_mime, original_payload)
        return ImageAttachment(
            original_path=original_path,
            original_mime=original_mime,
            model_path=original_path,
            model_mime=original_mime,
        )

    original = decode_data_url(image.original_url)
    model = decode_data_url(image.model_url)
    if original is None or model is None:
        raise ValueError("uploaded images must use base64 data URLs")

    original_mime, original_payload = original
    model_mime, model_payload = model
    return ImageAttachment(
        original_path=save_attachment_variant(thread, original_mime, original_payload),
        original_mime=original_mime,
        model_path=save_attachment_variant(thread, model_mime, model_payload),
        model_mime=model_mime,
    )


def persist_image_inputs(
    thread, images: list[str | ImageInput]
) -> list[ImageUrl | ImageAttachment]:
    return [persist_image_input(thread, image) for image in images]


def attachment_data_url(thread, attachment: ImageAttachment, *, original: bool) -> str:
    relative_path = attachment.original_path if original else attachment.model_path
    mime = attachment.original_mime if original else attachment.model_mime
    payload = resolve_attachment_path(thread, relative_path).read_bytes()
    return encode_data_url(mime, payload)


def resolve_message_attachments(messages: Messages, thread) -> Messages:
    """Return a provider-ready copy with attachment refs materialized."""
    if not any(
        isinstance(message.content, ImageAttachment) for message in messages.data
    ):
        return messages

    resolved = messages.model_copy(deep=True)
    for index, message in enumerate(resolved.data):
        content = message.content
        if not isinstance(content, ImageAttachment):
            continue
        resolved.data[index] = Message.user_image(
            attachment_data_url(thread, content, original=False),
            message_id=message.message_id,
            turn_id=message.turn_id,
        )
    return resolved


def migrate_inline_images(messages: Messages, thread) -> bool:
    """Move legacy inline data URLs into thread attachments."""
    migrated = False
    for index, message in enumerate(messages.data):
        content = message.content
        if not isinstance(content, ImageUrl):
            continue
        decoded = decode_data_url(content.url)
        if decoded is None:
            continue
        attachment = persist_image_input(thread, content.url)
        if not isinstance(attachment, ImageAttachment):
            continue
        messages.data[index] = Message.user_image_attachment(
            attachment,
            message_id=message.message_id,
            turn_id=message.turn_id,
        )
        migrated = True
    return migrated


async def save_images_to_sandbox(
    sandbox, images: list[str], *, subdir: str = "uploads"
) -> list[str]:
    """Compatibility helper for callers that explicitly need sandbox copies."""
    if sandbox is None:
        return []
    saved: list[str] = []
    for index, url in enumerate(images):
        decoded = decode_data_url(url)
        if decoded is None:
            continue
        mime, payload = decoded
        extension = MIME_EXTENSIONS.get(mime, "bin")
        digest = hashlib.sha256(payload).hexdigest()
        path = f"{subdir}/{digest}-{index}.{extension}"
        await sandbox.files.write(path, payload)
        saved.append(path)
    return saved
