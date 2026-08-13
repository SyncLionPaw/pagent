# pagentv4

语言：[中文](/zh/pagentv4/) | [English](/pagentv4/)

`pagentv4` 是本仓库中较新的类型化 API。

适合以下场景：

- 用 `Provider` 替代 `LLM`
- 用 `Message` / `Messages` 替代 `Session`
- 用 `Runner` 做基于 thread 的编排、持久化和 sandbox workspace
- 需要 **sandbox**（伴身电脑）提供文件与命令工具
- 需要 **Thread** 和 **Skill** 支撑长期 REPL 类应用

## 模块分层

```text
core/       AgentCore, Message, Provider, Tool, Event
runtime/    loop_core, Runner, VanillaRunner, Thread
conversation/ ConversationStore 实现，通过 Thread 使用
sandbox/    Backend, Sandbox, 内置文件/命令工具
adapters/   ACP 编解码
skills/     SKILL.md 发现与按需加载
```

`runtime/` 里有两层：

- `loop_core` 统一 run / turn / tool 的事件循环语义
- `Runner` 与 `VanillaRunner` 在这套共享循环外包上各自的运行环境

## 文档目录

- [快速开始](./quick-start)
- [核心类型](./core-types)
- [消息](./messages)
- [工具](./tools)
- [VS Code 插件](/zh/vscode)
- [Sandbox](./sandbox)
- [怎么选沙箱后端](./backends)（`local` / `inplace` / `docker` / `ssh`）

## 终端应用的 Provider 配置

`uv run pagent` 从 `~/.pagent/pagent.toml` 读取命名 Provider。先定义会用到的
Provider，再给主 Agent 选择其中一个：

```toml
[provider.deepseek]
kind = "deepseek"
model = "deepseek-v4-flash"
api_key = "" # 空值会读取 DEEPSEEK_API_KEY

[provider.local]
kind = "ollama"
model = "qwen3:8b"

[agent]
provider = "deepseek"
```

`kind` 可选 `openai`、`deepseek`、`kimi`、`mimo`、`longcat`、`ollama`、
`vllm` 和 `sglang`。需要覆盖内置服务地址时，在对应 Provider 中设置 `base_url`。

新建 thread 时，Provider 名称、kind、model 和 base URL 会写入 `thread.toml`。
API Key 继续保存在全局配置或环境变量中。

配置两个及以上 Provider 后，Desktop、Web 和 VS Code 的聊天界面会显示模型选择器。
切换从下一条消息生效，当前会话上下文会继续保留。handoff 记录保存在 thread 中，
恢复会话后会继续使用最后选择的 Provider。

## 状态说明

新工作请使用 `pagentv4` 与 `app`（终端 REPL）。顶层 `pagent` 包仍保留较旧的
`Session + LLM` API 文档。
