# pagentv5 examples

pagentv5 的最小可运行示例。分层很直接：

- **Provider** 负责身份凭据和 API 协议，`complete()` 产出模型无关的消息流。
- **Runner** 消费这条流，翻译成带 `run/turn/step` 上下文的事件对外产出。
- **Tool** 由 `@tool()` 从函数签名生成 schema，Runner 执行后把结果送回下一轮。

| 文件 | 内容 | 需要 API key |
|------|------|:---:|
| `providers.py` | Provider 的三种构造方式：具名、自带端点、同厂商多模型 | 否 |
| `quickstart.py` | 配一个 Provider，流式打印 `text_delta` | 是 |
| `events.py` | 全量订阅事件，观察一次 run 的完整生命周期 | 是 |
| `tools.py` | 注册函数工具，观察生成、执行、回传、再生成 | 是 |
| `resources.py` | 组合 Task、Sandbox、UserDir 和 Session | 否 |
| `sdk/base_agent.py` | 使用 BaseAgent | 是 |
| `sdk/base_agent_persistent.py` | 在当前目录持久化 BaseAgent 对话 | 是 |
| `sdk/local_workspace_agent.py` | 使用 LocalWorkspaceAgent 操作本地目录 | 是 |
| `sdk/sandbox_worker.py` | 使用 Podman SandboxWorker | 是 |
| `sdk/sandbox_worker_ssh.py` | 使用 SSH SandboxWorker | 是 |

## 运行

```bash
# 只构造 Provider 并打印身份，不发请求
uv run python -m examples.pagentv5.providers
uv run python -m examples.pagentv5.resources

# 需要真实 key
export DEEPSEEK_API_KEY="your-key-here"
uv run python -m examples.pagentv5.quickstart
uv run python -m examples.pagentv5.events
uv run python -m examples.pagentv5.tools
uv run python -m examples.pagentv5.sdk.base_agent
uv run python -m examples.pagentv5.sdk.base_agent_persistent
uv run python -m examples.pagentv5.sdk.local_workspace_agent
uv run python -m examples.pagentv5.sdk.sandbox_worker

# SSH 还需设置 PAGENT_SSH_HOST 和 PAGENT_SSH_USER
uv run python -m examples.pagentv5.sdk.sandbox_worker_ssh
```

## 事件序列

一次 run 的事件形如：

```text
run_start
  turn_start
    step_start
      response_start
      text_start / text_delta ... / text_end
      （若模型发起工具调用：tool_call_start / _delta / _end）
      response_end
    step_end
    step_start (tool_execution)
      tool_result
    step_end
  turn_end
run_end
```

`Runner(provider, event_types={"text_delta"})` 可只订阅关心的事件类型；
留空则全量透出。事件类型定义在 `pagentv5.events`。

## 工具

用 `@tool()` 声明函数，将工具传给 Runner：

```python
from pagentv5 import Runner, tool


@tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


runner = Runner(provider, tools=[add], max_turns=8)
```

一个 Turn 包含一次模型生成，以及模型请求时的一批工具执行。Runner 会把
`tool_result` 追加到输入并启动下一 Turn。达到 `max_turns` 后，Runner 会再运行
一个禁用工具的 synthesis Turn，让模型基于已有结果完成回答。

## 长时 Task

`TaskSpec` 冻结 Provider、Sandbox、UserDir 和 Session 配置。`ResourceService`
提供传输无关的 Task 创建、恢复、历史、文件树与运行接口。Wire、HTTP、RPC 和
Desktop IPC 的 endpoint 映射见
[resource endpoints](../../docs/pagentv5/resource-endpoints.md)。

## 便捷 SDK

三种 SDK 门面共享相同的 `run()`、`ask()` 和异步上下文接口：

```python
from pagentv5 import BaseAgent, LocalWorkspaceAgent, SandboxWorker
```

- `BaseAgent`：模型与自定义工具。
- `SandboxWorker`：附带独立 Sandbox 工作根。
- `LocalWorkspaceAgent`：将本地目录作为可读写工作根。

`emit_type="event"` 返回完整事件流，`emit_type="text"` 返回文本增量。
`max_turn` 是 `max_turns` 的便捷别名。`yolo=False` 时，工具调用需要通过
`approve_tool` 回调批准；未提供回调的工具调用会被拒绝并将结果反馈给模型。
