from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from . import settings

JWT_ALG = "HS256"


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_jwt(*, sub: str, username: str) -> str:
    now = int(time.time())
    header = {"alg": JWT_ALG, "typ": "JWT"}
    payload = {
        "sub": sub,
        "username": username,
        "iat": now,
        "exp": now + settings.JWT_TTL_SECONDS,
    }
    header_b64 = b64url_encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    payload_b64 = b64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(
        settings.JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    return f"{header_b64}.{payload_b64}.{b64url_encode(signature)}"


def verify_jwt(token: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise ValueError("invalid token format") from exc
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(
        settings.JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    actual = b64url_decode(signature_b64)
    if not hmac.compare_digest(actual, expected):
        raise ValueError("invalid token signature")
    payload = json.loads(b64url_decode(payload_b64).decode("utf-8"))
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise ValueError("token expired")
    return payload
