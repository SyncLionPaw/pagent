from __future__ import annotations

import argparse
import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

from pagentv4.core import (
    PROVIDER_TYPES,
    provider_api_key_env,
    provider_base_url,
    provider_requires_api_key,
)
from pagentv4.ithread import SubAgentSpec
from pagentv4.paths import (
    activate_home,
    default_pagent_home,
    find_home_config,
    home_config_path,
)
from pagentv4.tools import HARNESS_WEB_TOOL_NAMES

BUNDLED_CONFIG = Path(__file__).with_name("pagent.toml")
CONFIG_FILENAMES = ("pagent.toml",)
# 兼容旧名：用户级 home 下的配置路径（未解析项目模式时）。
USER_CONFIG_PATH = "~/.pagent/pagent.toml"
# runner 进程自身跑在哪：local = 用户电脑（当前唯一支持）；cloud = 云端 pod（保留，未接线）。
RUNNER_LOCATIONS = ("local", "cloud")
DEFAULT_PROVIDER_NAME = "deepseek"
DEFAULT_PROVIDER_KIND = "deepseek"
DEFAULT_MODEL = "deepseek-v4-flash"


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """一个命名 Provider；``kind`` 是构造具体 Provider 的判别字段。"""

    kind: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    # 该 provider 的模型是否支持图片输入。带图消息只会发给声明 vision = true 的
    # provider，避免把 image_url 发给纯文本模型触发 400。
    vision: bool = False

    def resolved_api_key(self) -> str | None:
        if self.api_key and self.api_key.strip():
            return self.api_key.strip()
        env = os.getenv(provider_api_key_env(self.kind))
        return env.strip() if env and env.strip() else None

    def resolved_base_url(self) -> str:
        return provider_base_url(self.kind, self.base_url)


@dataclass(slots=True)
class ReplConfig:
    thread_id: str | None = None
    blocking: bool = False
    model: str | None = None
    api_key: str | None = None
    provider_base_url: str | None = None
    providers: dict[str, ProviderConfig] | None = None
    agent_provider: str | None = None
    max_turns: int | None = None
    runner_location: str | None = None
    backend: str | None = None
    image: str | None = None
    container_ttl: int | None = None
    command_policy: str | None = None
    sandbox_tools: tuple[str, ...] | None = None
    project_path: str | None = None
    ssh_host: str | None = None
    ssh_config: str | None = None
    ssh_workdir: str | None = None
    skill_roots: tuple[str, ...] | None = None
    # 主 agent 的进程内（harness）工具白名单，冻结进新 thread.toml 的 [agent] tools。
    # None 表示未在 pagent.toml 显式配置，回退到默认（web 工具）。
    agent_tools: tuple[str, ...] | None = None
    # 命名子 agent：冻结进新 thread.toml 的 [sub.<name>]。None = 未配置。
    subs: dict[str, SubAgentSpec] | None = None
    user_label: str | None = None
    assistant_label: str | None = None
    permission_mode: str | None = None

    def resolved_provider_name(self) -> str:
        if self.agent_provider:
            return self.agent_provider
        if self.providers:
            if DEFAULT_PROVIDER_NAME in self.providers:
                return DEFAULT_PROVIDER_NAME
            if len(self.providers) == 1:
                return next(iter(self.providers))
            raise ValueError(
                "agent.provider is required when multiple providers are configured"
            )
        return "default"

    def resolved_provider(self) -> ProviderConfig:
        if self.providers:
            name = self.resolved_provider_name()
            try:
                return self.providers[name]
            except KeyError as exc:
                raise ValueError(
                    f"agent.provider references unknown provider {name!r}"
                ) from exc
        return ProviderConfig(
            kind=DEFAULT_PROVIDER_KIND,
            model=self.model or DEFAULT_MODEL,
            api_key=self.api_key,
            base_url=self.provider_base_url,
        )

    def provider_named(self, name: str) -> ProviderConfig:
        """按配置名取 Provider；旧单表配置使用其隐式名称 ``default``。"""
        normalized = name.strip()
        if self.providers:
            try:
                return self.providers[normalized]
            except KeyError as exc:
                raise ValueError(f"unknown provider {normalized!r}") from exc
        if normalized == self.resolved_provider_name():
            return self.resolved_provider()
        raise ValueError(f"unknown provider {normalized!r}")

    def vision_provider_name(self) -> str | None:
        """返回第一个声明 ``vision = true`` 的 provider 名；没有则 None。

        带图消息据此自动切到支持视觉的 provider；优先返回当前主 provider（若它
        本身支持视觉），否则按配置顺序取第一个 vision provider。
        """
        if not self.providers:
            provider = self.resolved_provider()
            return self.resolved_provider_name() if provider.vision else None
        current = self.resolved_provider_name()
        if self.providers.get(current) and self.providers[current].vision:
            return current
        for name, provider in self.providers.items():
            if provider.vision:
                return name
        return None

    def resolved_api_key(self) -> str | None:
        return self.resolved_provider().resolved_api_key()

    def requires_api_key(self) -> bool:
        return provider_requires_api_key(self.resolved_provider().kind)

    def resolved_max_turns(self) -> int:
        return self.max_turns if self.max_turns is not None else 24

    def resolved_runner_location(self) -> str:
        return self.runner_location if self.runner_location is not None else "local"

    def resolved_model(self) -> str:
        return self.resolved_provider().model

    def provider_for_thread(
        self,
        *,
        provider_name: str,
        provider_kind: str,
        model: str,
        base_url: str | None,
    ) -> ProviderConfig:
        """用 thread 冻结的身份字段配 Provider，凭据仍从全局配置或环境变量读取。"""
        configured = (self.providers or {}).get(provider_name)
        if configured is None and self.providers:
            same_identity = [
                provider
                for provider in self.providers.values()
                if provider.kind == provider_kind
                and provider.model == model
                and provider.resolved_base_url().rstrip("/")
                == (base_url or provider.resolved_base_url()).rstrip("/")
            ]
            if len(same_identity) == 1:
                configured = same_identity[0]
            else:
                same_kind = [
                    provider
                    for provider in self.providers.values()
                    if provider.kind == provider_kind
                ]
                if len(same_kind) == 1:
                    configured = same_kind[0]
        api_key = configured.api_key if configured is not None else None
        if not self.providers and provider_kind == DEFAULT_PROVIDER_KIND:
            api_key = self.api_key
        return ProviderConfig(
            kind=provider_kind,
            model=model,
            api_key=api_key,
            base_url=base_url,
        )

    def resolved_skill_roots(self) -> tuple[str, ...]:
        return self.skill_roots or ()

    def resolved_agent_tools(self) -> tuple[str, ...]:
        """冻结进 thread.toml 的 [agent] tools 白名单。

        未在 pagent.toml 显式配置时默认给全套 web 工具（保持既有行为，只是从静默
        挂载改成显式冻结）。显式配了（含空表）就照配置来。
        """
        if self.agent_tools is None:
            return HARNESS_WEB_TOOL_NAMES
        return self.agent_tools

    def resolved_skill_dirs(self) -> tuple[str, ...]:
        """把 ``[skills] roots`` 展开成冻结进 thread.toml 的 ``[agent] skills``。

        ``roots`` 就是完整扫描列表，不隐式追加任何目录：写了才扫，删了就没有。
        ``{pagent_home}``（兼容旧写法 ``{home}``）展开成当前生效的 pagent 数据根
        （prod/dev/PAGENT_HOME 由 activate_home 决定），让模板不必写死绝对路径。
        """
        pagent_home = str(default_pagent_home())
        return tuple(
            root.replace("{pagent_home}", pagent_home).replace("{home}", pagent_home)
            for root in self.resolved_skill_roots()
        )

    def resolved_user_label(self) -> str:
        label = (self.user_label or "you").strip()
        return label or "you"

    def resolved_assistant_label(self) -> str:
        label = (self.assistant_label or "pagent").strip()
        return label or "pagent"

    def resolved_permission_mode(self) -> str:
        mode = (self.permission_mode or "prompt").strip().lower()
        return mode if mode in ("prompt", "auto") else "prompt"

    def permission_auto(self) -> bool:
        return self.resolved_permission_mode() == "auto"

    def thread_overrides(self) -> dict:
        kwargs: dict = {}
        if self.backend is not None:
            kwargs["backend"] = self.backend
        if self.image is not None and self.image != "":
            kwargs["image"] = self.image
        if self.container_ttl is not None:
            kwargs["container_ttl_seconds"] = self.container_ttl or None
        if self.command_policy is not None:
            kwargs["command_policy"] = self.command_policy
        if self.sandbox_tools is not None:
            kwargs["sandbox_tools"] = self.sandbox_tools
        # project_path 是本次会话冻结进 thread.toml 的 host_root：留空时在这里
        # 解析成启动时的 cwd 绝对路径，让 thread.toml 写具体值（resume 不漂移）。
        # 全局 pagent.toml 里留空的语义仍是"用 cwd"，只是解析点前置到冻结时。
        if self.project_path is not None and self.project_path != "":
            kwargs["project_path"] = os.path.abspath(
                os.path.expanduser(self.project_path)
            )
        else:
            kwargs["project_path"] = os.path.abspath(os.getcwd())
        if self.ssh_config is not None:
            kwargs["ssh_config"] = self.ssh_config
        if self.ssh_host is not None and self.ssh_host != "":
            kwargs["ssh_host"] = self.ssh_host
        if self.ssh_workdir is not None:
            kwargs["ssh_workdir"] = self.ssh_workdir
        provider = self.resolved_provider()
        kwargs["provider_name"] = self.resolved_provider_name()
        kwargs["provider_kind"] = provider.kind
        kwargs["model"] = provider.model
        kwargs["provider_base_url"] = provider.resolved_base_url()
        # SSOT：把 harness 工具白名单与 skills 目录冻结进新 thread.toml，
        # 让 [agent] tools / [agent] skills 成为运行时唯一事实来源。
        kwargs["agent_tools"] = self.resolved_agent_tools()
        kwargs["skills"] = self.resolved_skill_dirs()
        if self.subs:
            kwargs["subs"] = dict(self.subs)
        return kwargs


def load_toml(path: Path) -> dict:
    with path.open("rb") as fp:
        return tomllib.load(fp)


def parse_provider_entry(name: str, payload: dict) -> ProviderConfig:
    kind = payload.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError(f"provider.{name}.kind must be a non-empty string")
    kind = kind.strip().lower()
    if kind not in PROVIDER_TYPES:
        raise ValueError(
            f"provider.{name}.kind must be one of {sorted(PROVIDER_TYPES)}"
        )

    model = payload.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"provider.{name}.model must be a non-empty string")

    api_key = payload.get("api_key")
    if api_key is not None and not isinstance(api_key, str):
        raise ValueError(f"provider.{name}.api_key must be a string")

    base_url = payload.get("base_url")
    if base_url is not None and not isinstance(base_url, str):
        raise ValueError(f"provider.{name}.base_url must be a string")

    vision = payload.get("vision", False)
    if not isinstance(vision, bool):
        raise ValueError(f"provider.{name}.vision must be a boolean")

    return ProviderConfig(
        kind=kind,
        model=model.strip(),
        api_key=api_key.strip() if api_key and api_key.strip() else None,
        base_url=base_url.strip() if base_url and base_url.strip() else None,
        vision=vision,
    )


def parse_provider_block(
    provider: dict,
) -> tuple[
    dict[str, ProviderConfig] | None,
    str | None,
    str | None,
    str | None,
]:
    """解析新命名 Provider 池；旧单表返回后三个兼容字段。"""
    legacy_keys = {"model", "api_key", "base_url"}
    has_legacy = bool(provider.keys() & legacy_keys)
    named = {name: value for name, value in provider.items() if name not in legacy_keys}
    if has_legacy and named:
        raise ValueError(
            "[provider] legacy fields cannot be mixed with [provider.<name>] tables"
        )

    if not named:
        model = provider.get("model")
        if model is not None and not isinstance(model, str):
            raise ValueError("provider.model must be a string")
        api_key = provider.get("api_key")
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError("provider.api_key must be a string")
        base_url = provider.get("base_url")
        if base_url is not None and not isinstance(base_url, str):
            raise ValueError("provider.base_url must be a string")
        return (
            None,
            model,
            api_key.strip() if api_key and api_key.strip() else None,
            base_url.strip() if base_url and base_url.strip() else None,
        )

    parsed: dict[str, ProviderConfig] = {}
    for name, payload in named.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("provider name must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError(f"provider.{name} must be a table")
        parsed[name] = parse_provider_entry(name, payload)
    return parsed, None, None, None


def parse_repl_config(data: dict) -> ReplConfig:
    provider = data.get("provider", {})
    if not isinstance(provider, dict):
        raise ValueError("provider must be a table")
    sandbox = data.get("sandbox", {})
    sandbox_container = sandbox.get("container", {})
    sandbox_ssh = sandbox.get("ssh", {})
    project = data.get("project", {})
    skills = data.get("skills", {})
    agent = data.get("agent", {})
    if not isinstance(agent, dict):
        raise ValueError("agent must be a table")
    repl = data.get("repl", {})
    runner = data.get("runner", {})
    permission = data.get("permission", {})

    max_turns = runner.get("max_turns")
    if max_turns is not None and not isinstance(max_turns, int):
        raise ValueError("runner.max_turns must be an integer")

    runner_location = runner.get("location")
    if runner_location == "":
        runner_location = None
    if runner_location is not None:
        if not isinstance(runner_location, str):
            raise ValueError("runner.location must be a string")
        if runner_location not in RUNNER_LOCATIONS:
            raise ValueError(f"runner.location must be one of {list(RUNNER_LOCATIONS)}")
        if runner_location == "cloud":
            raise NotImplementedError(
                "runner.location = 'cloud' 尚未支持；云端 pod 形态待实现，当前只支持 'local'"
            )

    providers, model, api_key, base_url = parse_provider_block(provider)
    agent_provider = agent.get("provider")
    if agent_provider is not None and not isinstance(agent_provider, str):
        raise ValueError("agent.provider must be a string")
    if isinstance(agent_provider, str):
        agent_provider = agent_provider.strip() or None
    if providers and agent_provider and agent_provider not in providers:
        raise ValueError(
            f"agent.provider references unknown provider {agent_provider!r}"
        )

    image = sandbox_container.get("image")
    if image == "":
        image = None

    command_policy = sandbox.get("command_policy")
    if command_policy is not None and not isinstance(command_policy, str):
        raise ValueError("sandbox.command_policy must be a string")
    if command_policy == "":
        command_policy = None

    container_ttl = sandbox_container.get("container_ttl")
    if container_ttl is not None and not isinstance(container_ttl, int):
        raise ValueError("sandbox.container.container_ttl must be an integer")

    tools = sandbox.get("tools")
    sandbox_tools: tuple[str, ...] | None
    if tools is None:
        sandbox_tools = None
    elif isinstance(tools, list):
        if not all(isinstance(item, str) for item in tools):
            raise ValueError("sandbox.tools must be a list of strings")
        sandbox_tools = tuple(item for item in tools if item.strip())
    else:
        raise ValueError("sandbox.tools must be a list of strings")

    # [project] 按 runner.location 分子表：local 绑用户目录(host_root)，
    # cloud 绑云端资源。location=cloud 已在上面 NotImplementedError 挡住，
    # 故这里只解析 [project.local]；[project.cloud] 是模板里的语义锚点。
    if "path" in project:
        raise ValueError(
            "顶层 [project] path 已废弃；改用 [project.local] path（按 runner.location 分模式）"
        )
    project_local = project.get("local", {})
    if not isinstance(project_local, dict):
        raise ValueError("[project.local] must be a table")
    project_path = project_local.get("path")
    if project_path is not None and not isinstance(project_path, str):
        raise ValueError("project.local.path must be a string")
    if project_path == "":
        project_path = None

    roots = skills.get("roots")
    skill_roots: tuple[str, ...] | None
    if roots is None:
        skill_roots = None
    elif isinstance(roots, str):
        skill_roots = (roots,) if roots.strip() else ()
    elif isinstance(roots, list):
        if not all(isinstance(item, str) for item in roots):
            raise ValueError("skills.roots must be a string or list of strings")
        skill_roots = tuple(item for item in roots if item.strip())
    else:
        raise ValueError("skills.roots must be a string or list of strings")

    agent_tools_cfg = agent.get("tools")
    agent_tools: tuple[str, ...] | None
    if agent_tools_cfg is None:
        agent_tools = None
    elif isinstance(agent_tools_cfg, list):
        if not all(isinstance(item, str) for item in agent_tools_cfg):
            raise ValueError("agent.tools must be a list of strings")
        agent_tools = tuple(item for item in agent_tools_cfg if item.strip())
    else:
        raise ValueError("agent.tools must be a list of strings")

    sub_block = data.get("sub")
    subs: dict[str, SubAgentSpec] | None
    if sub_block is None:
        subs = None
    elif not isinstance(sub_block, dict):
        raise ValueError("[sub] must be a table of [sub.<name>] entries")
    else:
        parsed: dict[str, SubAgentSpec] = {}
        for name, spec in sub_block.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("[sub.<name>] name must be a non-empty string")
            if not isinstance(spec, dict):
                raise ValueError(f"[sub.{name}] must be a table")
            parsed[name] = SubAgentSpec.from_dict(spec)
        subs = parsed

    user_label = repl.get("user_label")
    if user_label is not None and not isinstance(user_label, str):
        raise ValueError("repl.user_label must be a string")
    if user_label == "":
        user_label = None

    assistant_label = repl.get("assistant_label")
    if assistant_label is not None and not isinstance(assistant_label, str):
        raise ValueError("repl.assistant_label must be a string")
    if assistant_label == "":
        assistant_label = None

    permission_mode = permission.get("mode")
    if permission_mode is not None:
        if not isinstance(permission_mode, str):
            raise ValueError("permission.mode must be a string")
        permission_mode = permission_mode.strip().lower()
        if permission_mode not in ("prompt", "auto"):
            raise ValueError("permission.mode must be 'prompt' or 'auto'")

    return ReplConfig(
        model=model,
        api_key=api_key,
        provider_base_url=base_url,
        providers=providers,
        agent_provider=agent_provider,
        max_turns=max_turns,
        runner_location=runner_location,
        backend=sandbox.get("backend"),
        image=image,
        container_ttl=container_ttl,
        command_policy=command_policy,
        sandbox_tools=sandbox_tools,
        project_path=project_path,
        ssh_host=sandbox_ssh.get("host"),
        ssh_config=sandbox_ssh.get("config_path"),
        ssh_workdir=sandbox_ssh.get("workdir"),
        skill_roots=skill_roots,
        agent_tools=agent_tools,
        subs=subs,
        user_label=user_label,
        assistant_label=assistant_label,
        permission_mode=permission_mode,
    )


def find_project_config(workdir: str | None = None) -> Path | None:
    """当前 cwd 若为项目模式，返回其配置文件（含遗留 ``./pagent.toml``）。"""
    return find_home_config(workdir)


def find_user_config(workdir: str | None = None) -> Path | None:
    """当前生效 home 下的 ``pagent.toml``；不存在则返回 None。"""
    return find_home_config(workdir)


def load_config_file(path: Path) -> ReplConfig:
    return parse_repl_config(load_toml(path))


def merge_config(base: ReplConfig, override: ReplConfig) -> ReplConfig:
    fields = {}
    for name in ReplConfig.__dataclass_fields__:
        value = getattr(override, name)
        if value is None:
            continue
        fields[name] = value
    if override.providers is not None:
        fields.update(model=None, api_key=None, provider_base_url=None)
    elif any(
        value is not None
        for value in (override.model, override.api_key, override.provider_base_url)
    ):
        fields.update(providers=None, agent_provider=None)
    return replace(base, **fields)


def ensure_home_config(workdir: str | None = None) -> Path:
    """定位当前 home 的 ``pagent.toml``；不存在就从包内模板物化一份写盘。

    home 由入口的 ``activate_home`` 决定：``--dev`` → ``<root>/.pagent``，否则
    ``~/.pagent``。种子取已打包的 ``src/app/pagent.toml``（``src/template`` 不进
    wheel，安装版机器上没有），两份解析结果由测试锁死一致。
    """
    existing = find_home_config(workdir)
    if existing:
        return existing
    target = home_config_path(workdir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(BUNDLED_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def load_config(
    *,
    config_path: Path | str | None = None,
    workdir: str | None = None,
) -> ReplConfig:
    """从单一来源加载配置：当前 home 的 ``pagent.toml``（缺失则先从模板物化）。

    ``--config <file>`` 若传入，作为显式覆盖再叠一层。未设字段回落 ReplConfig
    自身默认（与模板一致），因此手删部分字段的 home 配置仍可正常工作。
    """
    source = ensure_home_config(workdir)
    config = load_config_file(source)

    if config_path is not None:
        explicit = Path(config_path).expanduser()
        if not explicit.is_file():
            raise FileNotFoundError(f"config not found: {explicit}")
        config = merge_config(config, load_config_file(explicit))

    return config


def refresh_provider_from_disk(
    config: ReplConfig, *, workdir: str | None = None
) -> ReplConfig:
    """从当前 home 的 ``pagent.toml`` 刷新 provider 字段。

    wire 进程启动时会缓存一份 ReplConfig；宿主（Desktop / VS Code）事后写入
    API Key 时，打开 runner 前调用本函数即可读到新 Key，无需重启进程。
    """
    fresh = load_config(workdir=workdir)
    if fresh.providers is not None:
        return replace(
            config,
            providers=fresh.providers,
            agent_provider=fresh.agent_provider,
            model=None,
            api_key=None,
            provider_base_url=None,
        )
    return replace(
        config,
        providers=None,
        agent_provider=None,
        model=fresh.model,
        api_key=fresh.api_key,
        provider_base_url=fresh.provider_base_url,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="pagent interactive REPL")
    parser.add_argument(
        "--config",
        default=None,
        help="extra config file over bundled + active home ({./.pagent|~/.pagent}/pagent.toml)",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="resume thread; omit to create thread-<timestamp>",
    )
    parser.add_argument(
        "--blocking",
        action="store_true",
        help="阻塞 REPL：跑完一轮再显示输入（默认 TTY 为底栏固定输入）",
    )
    parser.add_argument(
        "--auto",
        "--yolo",
        action="store_true",
        help="危险工具自动审批（等同 [permission] mode=auto）；--yolo 为别名",
    )
    parser.add_argument(
        "--permission-mode",
        choices=("prompt", "auto"),
        default=None,
        help="工具审批模式",
    )
    parser.add_argument(
        "--wire",
        action="store_true",
        help="stdio NDJSON 后端模式：stdin 收 JSON 命令，stdout 出事件流（供插件/前端驱动）",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="HTTP 后端模式：POST /command 收命令，GET /events 出 SSE 事件流（对齐 wire）",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="--http 监听地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8848,
        help="--http 监听端口（默认 8848）",
    )
    backend_group = parser.add_mutually_exclusive_group()
    backend_group.add_argument(
        "--backend",
        choices=("local", "inplace", "container", "docker", "podman", "ssh"),
        default=None,
        help="覆盖 sandbox backend",
    )
    backend_group.add_argument(
        "-C",
        "--inplace",
        metavar="PROJECT",
        default=None,
        help="直接编辑 PROJECT（等同 --backend inplace --project PROJECT）",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="绑定本次会话的用户目录（host_root）；存为绝对路径，避免 resume 漂移",
    )
    parser.add_argument(
        "--dev",
        nargs="?",
        const=".",
        default=None,
        metavar="ROOT",
        help="开发模式：数据落到 <ROOT>/.pagent（默认 ./.pagent）；不带则生产模式用 ~/.pagent",
    )
    parser.add_argument("--ssh-host", default=None, help="覆盖 SSH Host 别名")
    parser.add_argument("--ssh-config", default=None, help="覆盖 SSH config 路径")
    return parser


def config_from_args(args: argparse.Namespace) -> ReplConfig:
    if getattr(args, "dev", None) is not None:
        activate_home("dev", args.dev)
    else:
        activate_home("prod")
    config = load_config(config_path=args.config)
    fields: dict = {}
    if args.thread_id:
        fields["thread_id"] = args.thread_id
    if args.blocking:
        fields["blocking"] = True
    if args.permission_mode:
        fields["permission_mode"] = args.permission_mode
    if args.auto:
        fields["permission_mode"] = "auto"
    if args.backend:
        fields["backend"] = args.backend
    if args.inplace and args.project:
        raise ValueError("-C/--inplace cannot be combined with --project")
    if args.inplace:
        fields["backend"] = "inplace"
        fields["project_path"] = os.path.abspath(os.path.expanduser(args.inplace))
    if args.project:
        # 归一化成绝对路径：thread.toml 存字面量，相对路径 resume 时会随 cwd 漂移。
        fields["project_path"] = os.path.abspath(os.path.expanduser(args.project))
    if args.ssh_host:
        fields["ssh_host"] = args.ssh_host
    if args.ssh_config:
        fields["ssh_config"] = args.ssh_config
    if fields:
        config = replace(config, **fields)
    return config
