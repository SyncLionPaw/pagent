"""把 ReplConfig 序列化成给前端展示的 JSON：api_key 脱敏，只回是否已配置。

wire / http 的 ``get_config`` 命令用它下发配置快照，前端据此渲染设置面板；
``set_provider`` 写盘后也回读一份快照确认生效。api_key 从不原样下发。
"""

from __future__ import annotations

from pagentv4 import provider_requires_api_key

from .config import ProviderConfig, ReplConfig


def mask_api_key(api_key: str | None) -> str:
    """脱敏：只保留尾部 4 位，其余用 * 遮蔽；空则返回空串。"""
    key = (api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 4:
        return "*" * len(key)
    return "*" * (len(key) - 4) + key[-4:]


def provider_to_public_dict(name: str, provider: ProviderConfig) -> dict:
    resolved_key = provider.resolved_api_key()
    return {
        "name": name,
        "kind": provider.kind,
        "model": provider.model,
        "base_url": provider.resolved_base_url(),
        "vision": provider.vision,
        "api_key_masked": mask_api_key(resolved_key),
        "api_key_configured": bool(resolved_key),
        "api_key_required": provider_requires_api_key(provider.kind),
    }


def config_to_public_dict(config: ReplConfig) -> dict:
    """ReplConfig → 面向前端的字典。api_key 脱敏，附 configured 布尔位。"""
    provider_name = config.resolved_provider_name()
    provider = config.resolved_provider()
    providers = config.providers or {provider_name: provider}
    return {
        "provider": provider_to_public_dict(provider_name, provider),
        "providers": [
            provider_to_public_dict(name, item) for name, item in providers.items()
        ],
        "sandbox": {
            "backend": config.backend or "",
            "image": config.image or "",
            "command_policy": config.command_policy or "",
        },
        "runner": {
            "location": config.resolved_runner_location(),
            "max_turns": config.resolved_max_turns(),
        },
        "permission": {
            "mode": config.resolved_permission_mode(),
        },
        "project": {
            "path": config.project_path or "",
        },
    }
