# pagentv5 SDK

pagentv5 提供三种便捷 Agent。`BaseAgent` 继承 `Runner`，
`SandboxWorker` 和 `LocalCodeAgent` 继承 `BaseAgent`，并根据用途装配不同资源。

| SDK | 持有资源 | 适用场景 |
|---|---|---|
| `BaseAgent` | Session、显式传入的工具 | 对话、业务函数工具 |
| `SandboxWorker` | Session、独立 Sandbox 工作根 | 生成文件、执行命令、隔离工作区 |
| `LocalCodeAgent` | Session、读写 UserDir | 编辑本地代码项目 |

## BaseAgent

```python
from pagentv5 import BaseAgent

agent = BaseAgent(
    "deepseek-v4-flash",
    provider_id="deepseek",
    max_turns=32,
    emit_type="text",
)

answer = await agent.ask("解释尾递归。")
await agent.close()
```

Agent 默认持有 memory Session，会保留实例内多次 `run()` 的消息历史。`clear()`
清空 Session 并保留 system message。

## Session

传入 `SessionConfig` 可以跨进程恢复对话：

```python
from pagentv5 import BaseAgent, SessionConfig

agent = BaseAgent(
    "deepseek-v4-flash",
    session=SessionConfig(
        storage="jsonl",
        session_id="my-agent",
    ),
)
```

`storage` 支持 `memory`、`jsonl` 和 `sqlite`。相对路径默认解析到 pagent 用户目录；
也可以通过 `session_base_path` 指定基准目录。Agent 接受已打开的 `Session` 实例，
并在 `close()` 时关闭它。Runner 在每次运行前读取 Session，运行结束后保存完整
Provider transcript。

## LocalCodeAgent

```python
from pagentv5 import LocalCodeAgent

async with LocalCodeAgent(
    "deepseek-v4-flash",
    provider_id="deepseek",
    project_path="./my-project",
    yolo=True,
    emit_type="text",
) as agent:
    async for text in agent.run("修复测试失败。"):
        print(text, end="")
```

`project_path` 会成为工作根，Agent 获得 `run_command`、`read_file`、
`write_file`、`str_replace` 和 `list_dir`。

## SandboxWorker

```python
from pagentv5 import SandboxWorker

async with SandboxWorker(
    "deepseek-v4-flash",
    provider_id="deepseek",
    workspace_path="./agent-workspace",
    sandbox_backend="local",
    yolo=True,
    emit_type="text",
) as agent:
    print(await agent.ask("创建 report.md。"))
```

省略 `workspace_path` 时使用临时目录，`close()` 会删除该目录。显式目录会保留。
`sandbox_backend` 支持 `local`、`container` 和 `ssh`。容器还需传
`sandbox_image`，SSH 还需传 `sandbox_connection`。

容器也可以使用紧凑写法：

```python
worker = SandboxWorker(
    "deepseek-v4-flash",
    sandbox="container:podman:docker.io/library/debian:bookworm-slim",
)
```

可用格式为 `local`、`ssh`、`container:<image>` 和
`container:<docker|podman>:<image>`。

## 输出

```python
async for event in agent.run("hello", emit_type="event"):
    print(event.type)

async for text in agent.run("hello", emit_type="text"):
    print(text, end="")
```

`event` 返回完整 `RunnerEvent`。`text` 只返回 `TextDeltaEvent.delta`。
`ask()` 收集 text 流并返回完整字符串。

## 工具审批

`yolo=True` 会直接执行工具。`yolo=False` 使用 `approve_tool` 决定每次调用：

```python
async def approve(call):
    return call.name in {"read_file", "list_dir"}


agent = LocalCodeAgent(
    "deepseek-v4-flash",
    project_path=".",
    approve_tool=approve,
)
```

回调接收完整 `ToolCallEnd`，可以检查名称、参数和 tool call ID。拒绝结果会作为
tool result 返回模型。

## Provider 参数

三个 SDK 都接受以下 Provider 参数：

- `provider_id`
- `api_protocol`
- `base_url`
- `api_key`
- `request_kwargs`
- `max_retries`

也可以传入实现 `ProviderProtocol` 的 `provider`，便于测试或接入自定义 Provider。
`max_turn` 是 `max_turns` 的别名；二者不能同时传入。
