from __future__ import annotations

import os


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = env(name, "1" if default else "0").lower()
    return raw in {"1", "true", "yes", "on"}


JWT_SECRET = env("CLOUD_JWT_SECRET", "cloud-dev-secret")
JWT_TTL_SECONDS = int(env("CLOUD_JWT_TTL_SECONDS", str(24 * 60 * 60)))

DATABASE_URL = env(
    "CLOUD_DATABASE_URL",
    "postgresql://pagent:pagent@127.0.0.1:5432/pagent",
)

S3_ENDPOINT_URL = env("CLOUD_S3_ENDPOINT_URL", "http://127.0.0.1:9000")
S3_ACCESS_KEY = env("CLOUD_S3_ACCESS_KEY", "pagent")
S3_SECRET_KEY = env("CLOUD_S3_SECRET_KEY", "pagentminio")
S3_BUCKET = env("CLOUD_S3_BUCKET", "pagent-artifacts")
S3_REGION = env("CLOUD_S3_REGION", "us-east-1")

CORS_ORIGINS = [
    item.strip()
    for item in env(
        "CLOUD_CORS_ORIGINS",
        "http://127.0.0.1:5174,http://localhost:5174,http://127.0.0.1:8080,http://localhost:8080",
    ).split(",")
    if item.strip()
]

DEMO_MODE = env_bool("CLOUD_DEMO_MODE", True)
DEMO_USERNAME = env("CLOUD_DEMO_USERNAME", "admin")
DEMO_PASSWORD = env("CLOUD_DEMO_PASSWORD", "123")

RUNTIME_ROOT = env("CLOUD_RUNTIME_ROOT", "/var/pagent/runtime")

LLM_API_KEY = env("CLOUD_LLM_API_KEY")
LLM_MODEL = env("CLOUD_LLM_MODEL", "deepseek-v4-flash")
LLM_BASE_URL = env("CLOUD_LLM_BASE_URL", "https://api.deepseek.com")
