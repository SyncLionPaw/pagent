# pagentv5 resource endpoints

pagentv5 将 Task、Session、Sandbox、UserDir 的实现放在传输层下面。CLI 可以直接
调用 Python 方法，Wire、HTTP、RPC 和 Desktop IPC 可以在这些方法外包装参数校验、
鉴权与序列化。

统一实现入口是 `pagentv5.service.ResourceService`。机器可读清单由
`pagentv5.service.endpoint_inventory()` 返回。

## Resource endpoints

| Endpoint | 实现函数 | 返回 |
|---|---|---|
| `task.create` | `ResourceService.create_task` | Task 详情 |
| `task.open` | `ResourceService.open_task` | Task 详情 |
| `task.list` | `ResourceService.list_tasks` | Task 摘要列表 |
| `task.get` | `ResourceService.task_details` | 配置、元信息、工具能力 |
| `task.metadata.update` | `ResourceService.update_task_metadata` | 更新后的元信息 |
| `task.delete` | `ResourceService.delete_task` | 无；当前实现为软删除 |
| `session.get` | `ResourceService.session_messages` | 结构化消息列表 |
| `session.replace` | `ResourceService.replace_session` | 保存后的消息列表 |
| `session.clear` | `ResourceService.clear_session` | 无 |
| `sandbox.status` | `ResourceService.sandbox_status` | backend、alive、workdir |
| `sandbox.tree` | `ResourceService.sandbox_tree` | 工作根文件树 |
| `sandbox.file.read` | `ResourceService.read_sandbox_file` | bytes |
| `userdir.status` | `ResourceService.userdir_status` | access、path |
| `userdir.tree` | `ResourceService.userdir_tree` | 用户目录文件树 |
| `userdir.file.read` | `ResourceService.read_userdir_file` | bytes |
| `task.capabilities` | `ResourceService.capabilities` | Provider、工具和资源摘要 |
| `run.start` | `ResourceService.run` | `RunnerEvent` 异步流 |
| `run.cancel` | `ResourceService.cancel_run` | 是否找到活动运行 |

`run.start` 会从 Task 取得 Provider 配置、Sandbox/UserDir 投影工具，并把 Task 的
Session 注入 Runner。Runner 在运行前组合 Session 历史，运行结束后提交完整
Provider transcript。

## Existing Wire commands

现有 `src/app/wire.py` 接收以下命令。Task 命名替代 Thread 命名后，资源命令按下表
迁移。

| Wire command | 新 endpoint / 归属 |
|---|---|
| `reset` | `task.create` |
| `resume` | `task.open` |
| `list_threads` | `task.list` |
| `thread_meta` | `task.get` |
| `delete_thread` | `task.delete` |
| `history` | `session.get` |
| `sandbox_status` | `sandbox.status` |
| `sandbox_tree` | `sandbox.tree` |
| `capabilities` | `task.capabilities` |
| `user` | `run.start` |
| `cancel` | `run.cancel` |
| `handoff_provider` | Runtime control；后续接入 Task 的 Provider handoff 记录 |
| `permit` / `deny` | Runtime approval；接入工具执行前 hook |
| `commands` | Application command catalog |
| `client_features` | Transport session negotiation |
| `get_config` | Application config service |
| `set_provider` | Application config service；凭据不写入 Task |
| `environment_check` | Host environment service |
| `skills` | Skill registry service |

Wire 输出仍包含运行事件，以及控制事件
`HistoryReplay`、`CurrentThread`、`ThreadList`、`ThreadMeta`、`ThreadTitle`、
`SandboxStatus`、`SandboxTree`、`Capabilities`、`Skills`、`SlashCommands`、
`SlashResult`、`ProviderState`、`ProviderHandoff`、`ConfigSnapshot`、
`EnvironmentCheck`、`PermitRequest`、`SubagentEvent` 和 `Error`。

新传输层应将其中的 Thread 字段改成 Task 字段：

| 旧事件 | 新事件名 |
|---|---|
| `CurrentThread` | `CurrentTask` |
| `ThreadList` | `TaskList` |
| `ThreadMeta` | `TaskMeta` |
| `ThreadTitle` | `TaskTitle` |
| `HistoryReplay` | 保留；字段使用 `task_id` |

模型运行事件直接编码 `pagentv5.events.RunnerEvent`，事件名取 `type`，payload 使用
Pydantic `model_dump()`。

## Existing HTTP routes

| HTTP route | 新 endpoint / 归属 |
|---|---|
| `GET /events` | 传输层事件订阅 |
| `POST /command` | 兼容 Wire 命令的传输适配 |
| `GET /api/health` | Host health service |
| `GET /api/app-info` | Host application service |
| `GET /api/runtime-state` | `task.get` + `sandbox.status` + 活动 run 状态 |
| `POST /api/yolo` | Runtime approval policy |
| `GET /api/settings` | Application config service |
| `GET /api/artifacts` | `userdir.tree`，约定 path=`artifacts` |
| `GET /api/artifacts/read` | `userdir.file.read` |
| `POST /api/artifacts/open` | Host file-open service |
| `GET /api/project-files` | `userdir.tree` |
| `GET /api/project-tree` | `userdir.tree` |
| `GET /api/new-session-options` | TaskSpec option catalog |
| `GET /api/thread-meta/{id}` | `task.get` |
| `POST /api/project-path` | 新建 Task 时写入 `UserDirConfig` |

## Existing VS Code messages

VS Code Webview 发出的消息完整集合：

| Webview message | 新 endpoint / 归属 |
|---|---|
| `userInput` | `run.start` |
| `requestHistoryReplay` | `session.get` |
| `setSandboxTarget` | 新建 Task 的 `SandboxConfig`；已有 Task 配置保持冻结 |
| `setYoloMode` | Runtime approval policy |
| `requestRuntimeOptions` | TaskSpec option catalog + Host environment service |
| `requestSlashCommands` | Application command catalog |
| `handoffProvider` | Runtime control |
| `permit` / `deny` | Runtime approval |
| `cancelRun` | `run.cancel` |

VS Code 当前还会直接发送
`commands`、`get_config`、`list_threads`、`history`、`reset`、`resume`、
`client_features`、`capabilities`、`handoff_provider`、`permit`、`deny`、
`cancel` 和 `user`。这些命令可由 Wire adapter 映射到上面的 endpoint。

## Existing Desktop IPC

Desktop IPC 分为共享资源、运行控制和宿主能力。

共享资源：

- `desktop:list-threads` → `task.list`
- `desktop:get-thread-meta` → `task.get`
- `desktop:resume-thread` → `task.open`
- `desktop:delete-thread` → `task.delete`
- `desktop:reset-session` → `task.create`
- `desktop:request-history` → `session.get`
- `desktop:get-sandbox-status` → `sandbox.status`
- `desktop:list-sandbox-tree` → `sandbox.tree`
- `desktop:list-project-files` / `desktop:list-project-tree` → `userdir.tree`
- `desktop:list-artifacts` / `desktop:read-artifact` → `userdir.tree` /
  `userdir.file.read`
- `desktop:send-user-input` → `run.start`

运行控制：

- `desktop:set-yolo-mode`
- `desktop:send-wire-command`
- `desktop:permit-tool-call`
- `desktop:deny-tool-call`
- `desktop:clear-last-error`

宿主能力：

- `desktop:get-app-info`
- `desktop:get-runtime-state`
- `desktop:get-settings`
- `desktop:open-documentation`
- `desktop:open-artifact`
- `desktop:select-project`
- `desktop:pick-directory`
- `desktop:get-new-session-options`
- `desktop:get-onboarding-state`
- `desktop:refresh-environment-check`
- `desktop:install-pagent-cli`
- `desktop:save-provider-setup`
- `desktop:complete-onboarding`

宿主能力保留在 Desktop 主进程。远程 HTTP 部署可以提供对应 Host service；核心资源
层无需依赖 Electron、VS Code 或 FastAPI。

## Transport wrapper rules

1. Wrapper 负责鉴权、超时、bytes 编码、错误码和连接生命周期。
2. Wrapper 不直接读取 Task 目录、Session 文件、Sandbox backend 或 UserDir 路径。
3. Task 配置只在 `task.create` 时写入，恢复任务使用 `task.open` 读取 `task.toml`。
4. API key、审批决定和客户端 feature negotiation 保持在运行时，不写入 `task.toml`。
5. `ResourceService.close()` 在进程或请求作用域结束时释放已打开的 Sandbox 和
   Session。
