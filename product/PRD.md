# pagent 产品需求文档

- 状态：Draft
- Owner：
- 最后确认：
- 适用版本：

## 1. 产品定位

<!-- 一句话讲清 pagent 是什么、给谁用、解决什么问题 -->

## 2. 目标用户与核心场景

<!-- 主要用户画像；每类用户的核心使用场景 -->

## 3. 产品形态

pagent 以同一套 pagentv4 内核对外提供多个入口：

- CLI：`uv run pagent`
- Desktop
- VS Code 插件
- Web UI

<!-- 各形态的定位差异与侧重 -->

## 4. 核心用户流程

<!-- 从启动到完成一次任务的关键路径；配置、会话、模型切换、沙箱选择等 -->

## 5. 功能需求与验收标准

<!-- 按功能模块列需求；每条给出可验证的验收标准 -->

## 6. 非目标与边界

<!-- 明确不做什么，划清范围 -->

## 7. 关键产品决策

### 7.0 Runner 依赖四个平级资源

一次运行由 Runner 编排，它平级持有四个外部资源。四者互不依赖，用户各自声明，组合出一次运行的完整环境。

| 资源 | 是什么 | 有生命周期（close）？ | 投影工具？ |
|------|--------|----------------------|-----------|
| **Provider** | 模型接入点，`complete()` 调模型 | 否（无状态 HTTP） | 否（是调用能力） |
| **Sandbox** | agent 自己的电脑，命令在哪跑 | 是（进程 / 容器 / SSH 会话） | 是 |
| **UserDir** | 用户的目录，碰不碰用户文件 | 否（是一段路径 + 权限） | 是 |
| **Session** | 对话历史存哪、怎么存 | 是（文件句柄 / SQLite 连接） | 否（Runner 基础设施，agent 不感知） |

两个属性把四个资源区分清楚，避免误解：

- **有无生命周期**：只有 Sandbox 和 Session 需要 open/close，子 agent 委派时要管归属（owned / borrowed）。Provider 无状态、UserDir 只是路径 + 权限，都不需要 close。
- **投不投影工具**：Sandbox 和 UserDir 会投影出 agent 能用的文件/命令工具（见 7.3）；Provider 是 agent 的调用能力不算工具；Session 只服务 Runner，agent 完全不感知。

7.1–7.5 展开 Sandbox 与 UserDir 这对投影工具的资源；7.6 说明 Session；7.7 说明 Skills——它不是平级资源，而是挂在「工作根」上的第二层资源，挂载点随资源组合动态决定。

### 7.1 执行环境拆成两个正交资源：Sandbox 与 UserDir

agent 能碰到的执行环境，由两个互不依赖的资源组合而成，Runner 平级持有：

- **Sandbox**：agent 自己的电脑。决定「命令在哪跑」。取值 `none`（没有沙箱）/ `local`（本机工作区）/ `container`（容器）/ `ssh`（远程主机）。
- **UserDir**：用户的目录。决定「碰不碰用户文件、怎么碰」。取值 `none`（碰不到）/ `readonly`（只能看和取）/ `readwrite`（能改）。

两个资源各自独立取值，产品形态是二者组合出来的坐标点，不是一个个单独实现的模式。

| Sandbox | UserDir | 是什么 |
|---------|---------|--------|
| `none` | `none` | 纯对话，只有进程内工具（web_search / fetch_url） |
| `none` | `readonly` | 只读检视用户目录，没有执行环境 |
| `none` | `readwrite` | **Cursor 模式**：agent 直接在用户目录里读写（即原 inplace） |
| `local`/`container`/`ssh` | `none` | **Workbuddy**：agent 在自己沙箱里干活，看不见用户文件 |
| `local`/`container`/`ssh` | `readonly` | 沙箱干活 + 观察/取用户文件（即原 local backend） |
| `local`/`container`/`ssh` | `readwrite` | 沙箱干活 + 能写回用户目录 |

这样取消了原来的 `inplace` backend：它不再是一个特殊模式，而是「无 Sandbox + UserDir 读写」这个坐标点。`backend` 这个词过去把「命令在哪跑」和「碰不碰用户目录」焊死成一个值，拆开后两件事各自独立。

UserDir = `none` 是真的碰不到用户文件：不投影任何桥接工具，`host_root` 保持为空，**禁止兜底到进程 cwd**。现状里空 `host_root` 会回退 `os.getcwd()`，导致 agent 在启动目录下「半可见」，新模型必须去掉这个兜底。

### 7.2 工作根由两轴推导，不单独配置

agent 的命令 cwd 和文件工具的根目录，是唯一的「工作根」，由两个资源推导得出，用户不单独配：

- 有 Sandbox → 工作根 = Sandbox。UserDir 通过桥接工具访问。
- 无 Sandbox + UserDir 读写 → 工作根 = UserDir，agent 直接在用户目录里干活（Cursor 模式，没有桥，因为没有第二个目录）。
- 无 Sandbox + UserDir 只读 → 没有工作根，只能看文件。
- 两者都无 → 没有任何文件/命令工具。

### 7.3 工具跟着资源走：compose_tools 纯函数

工具集不再由用户手写白名单，而是从两个资源的配置**静态推导**出来。核心是一个纯函数：输入两个资源配置，输出工具名列表，不启动沙箱、不读文件系统，可脱离运行时单测。

```python
WORKROOT_TOOLS = ("run_command", "read_file", "write_file", "str_replace", "list_dir")

def compose_tools(sandbox, userdir) -> list[str]:
    # 无沙箱 + 用户目录可写 → 用户目录升格为工作根（Cursor 模式，无桥）
    if sandbox.backend == "none" and userdir.access == "readwrite":
        return list(WORKROOT_TOOLS)

    # 无沙箱 + 用户目录只读 → 只能看
    if sandbox.backend == "none" and userdir.access == "readonly":
        return ["list_host_files"]

    # 无沙箱 + 无用户目录 → 纯对话
    if sandbox.backend == "none":
        return []

    # 有沙箱：工作根是沙箱，五个文件工具落在沙箱里
    tools = list(WORKROOT_TOOLS)

    # 用户目录通过桥接访问，按权限增量叠加
    if userdir.access == "readonly":
        tools += ["list_host_files", "copy_from_host"]
    elif userdir.access == "readwrite":
        tools += ["list_host_files", "copy_from_host", "copy_to_host"]

    return tools
```

每个坐标点投影出的工具：

| Sandbox | UserDir | 工具 |
|---------|---------|------|
| `none` | `none` | （空） |
| `none` | `readonly` | `list_host_files` |
| `none` | `readwrite` | 5 个工作根工具 |
| `local`/`container`/`ssh` | `none` | 5 个工作根工具 |
| `local`/`container`/`ssh` | `readonly` | 5 + `list_host_files` + `copy_from_host` |
| `local`/`container`/`ssh` | `readwrite` | 5 + `list_host_files` + `copy_from_host` + `copy_to_host` |

好处：用户只声明资源和权限，工具集、提示词描述、审批策略都从这一个函数派生，单一事实源。原来的 `[sandbox] tools` 手写白名单退场；如需收窄，只作为「在推导出的工具集上再做减法」的可选覆盖。

UserDir 权限档的语义边界划在「能不能写回用户目录」：

- `readonly` = 能看能取：`list_host_files` 观察 + `copy_from_host` 把用户文件取进沙箱处理。取进沙箱后 agent 能读到全文，但改动落在沙箱工作区，不回流用户目录，所以仍算只读。不再细分「只能列名字、不能取内容」这种更细的档位。
- `readwrite` = 在 readonly 基础上加 `copy_to_host`（有 Sandbox 时）或直接文件工具（Cursor 模式）。`copy_to_host` 可写到用户目录下任意子路径（受工作根越界检查约束），不再锁死 `artifacts/`——那是旧 local 时代的限制，readwrite 既然给了完整写权限就不该再锁。

### 7.4 合法性校验：读写要求同机

UserDir = `readwrite` 的本质是 agent 在用户目录里直接干活，要求沙箱与用户目录在同一物理机。组合前就要拒绝非法配置，不等运行时报错：

- `local` / `container` Sandbox + UserDir `readwrite` → 合法。`local` 直接同机；`container` 通过 bind mount（`-v <userdir>:<userdir>` 同路径挂载）让容器直接改宿主目录。
- `ssh` Sandbox + UserDir `readwrite` → 非法：沙箱在远端，用户目录在本机，跨机写不回去。ssh 下 UserDir 只能是 `none` / `readonly`（走桥接，文件经连接传输）。

### 7.5 配置形态

用户配置面收缩为两个独立块，各一个枚举：

```toml
[sandbox]
backend = "local" # none | local | container | ssh

[userdir]
access = "readonly"        # none | readonly | readwrite
path = ""                  # readonly/readwrite 时必填；none 时忽略且不兜底 cwd
```

这是 `task.toml` 语义级的破坏性变更：原先同时表达执行环境与用户目录权限的顶层 `backend`，拆成 `[sandbox] backend` + `[userdir] access` 两个字段，需要处理持久化迁移。

### 7.6 Session：对话历史资源

Session 是 Agent/Runner 持有的第四个资源，不投影任何工具。它的后端满足
`save` / `load` / `list` / `delete` 协议，可替换存储实现。

| 取值 | 含义 |
|------|------|
| `memory` | 不落盘，进程内，退出即丢 |
| `jsonl` | 一对话一文件，人可读（默认） |
| `sqlite` | 单表多行，适合量大 / 需索引 |

职责边界：**`task.toml` 是 Task 身份的唯一事实源**（哪个 Provider / Sandbox / UserDir / Session 被冻结），**Session 后端只管对话内容**（messages）。换存储后端（jsonl ↔ sqlite）不影响冻结的身份。两者都在 Task 目录下，但职责分开。

它和 Sandbox 一样有 open/close 生命周期（文件句柄 / SQLite 连接），子 agent 委派时同样按 owned / borrowed 管归属，弹帧只关自己开的那份。

### 7.7 Skills：挂在工作根上的第二层资源

Skills 是资源，但不是 Runner 的平级资源。它挂在「工作根」上，挂载点随资源组合动态决定，与 7.2 的工作根推导一致：

| Sandbox | UserDir | Skills 挂哪 |
|---------|---------|-------------|
| 有 | 任意 | 挂 Sandbox |
| 无 | `readwrite` / `readonly` | 挂 UserDir |
| 无 | 无 | 无处可挂，skills 不生效（纯对话） |

这样 Cursor 模式（无 Sandbox + UserDir 读写）也能用 skills——挂到升格为工作根的 UserDir，不再像现在那样硬绑 Sandbox、无沙箱就用不了。

Skills 的其他性质：

- **只投影一个工具 `use_skill`**：把某个 skill 的完整指令按需塞进上下文。skill 本身不绑定新工具；要跑脚本就让 agent 用 `run_command` 执行 skill 目录下的脚本。
- **无生命周期**：`SkillRegistry` 是内存里「名字 → skill」的索引，扫目录得到，不需要 close。
- **system prompt 只放摘要**：启动时只把每个 skill 的 name + description 汇总进 system prompt，模型显式调 `use_skill(name)` 才加载完整指令。

### 7.8 运行策略归属

V5 资源层直接执行 `run_command`，不扫描或改写 shell 指令。核心保留超时、输出大小、
资源限制和结构化结果。工具审批由 Runner hook 或应用层处理，隔离边界由容器、SSH
账户及宿主权限提供。
- **审批策略不变**：`permission.mode`（prompt / auto）是另一回事，保持现状，不并进这套插件。

待定（后面再定，先不锁死）：是否开放用户注册自定义护栏、是否支持多条护栏叠加、要不要把人工审批也统一到这套插件机制里。

### 7.9 运行模型：Run / Turn / Step

一次运行分三级，从粗到细：

**Run** —— 一次运行，处理一个触发，从 `RunBegin` 到 `RunEnd`。内含 1 到 `max_turns` 个 Turn。

**Turn** —— 一轮「模型说话 + 工具干活」。模型生成一次，再把它这轮要的工具全部跑完，是一个 Turn。边界事件 `TurnBegin` / `TurnEnd`。`TurnEnd(continuing)` 表示还有下一轮，其它 stop_reason 表示 Run 结束。

**Step** —— Turn 内的阶段，对应 `run_state.phase` 已有的两个值：

| Step | phase | 干什么 | 产出 |
|---|---|---|---|
| 生成 Step | `generating` | 模型流式输出 | `TextDelta` / `ReasoningDelta` / `ToolCallBegin` → `TurnResult` |
| 工具 Step | `calling` | 执行这一轮的所有工具调用 | 每个工具一个 `ToolResult` |

规则：

- 生成 Step 一定有，工具 Step 不一定。模型这轮没要求调工具（`no_tool_calls`），就只有生成 Step，Turn 随即结束 Run。
- 工具 Step 是一批，不是一个。一个 Turn 里模型可能要求多个工具调用，它们在同一个工具 Step 内执行完。单个工具调用不构成 Step。
- Turn 数用尽时多跑一个收尾轮（synthesis turn），内部只有生成 Step 且强制不给工具，让模型做总结；仍落在这个三级模型里。

一句话：Run 是一次任务，由若干 Turn 组成，每个 Turn 是模型说一次话再把它要的工具跑一遍；Turn 内分生成 Step 和工具 Step。模型不再要工具时，当前 Turn 收尾，Run 结束。

事件流为三级运行边界都提供事件：`RunStart` / `RunEnd`、`TurnStart` / `TurnEnd`、`StepStart` / `StepEnd`。UI 可以按 Step 分组渲染，运行状态也从同一套事件恢复。

### 7.10 Run 的触发来源

现在 Run 入口是 `run(user_input: str)`，一路到 `RunBegin(user_input)` 都是裸字符串，只能表达「用户打了字」。后续要支持定时任务、goal hook 回调这类非用户触发，得把触发抽象成一个带类型标签的 **Trigger**：

| kind | 携带内容 | 场景 |
|---|---|---|
| `user` | `text` | 用户输入（现状） |
| `schedule` | 触发时间 + payload | 定时任务 |
| `goal` | goal_id + hook 名 + payload | goal hook 回调 |

三种触发的共性：都携带一段喂给模型的内容 + 一个来源标识。Run 入口从 `run(user_input)` 变成 `run(trigger)`，`RunBegin` 携带 `trigger`。

一个待定的实现级取舍：`RunBegin` 是保留 `user_input` 再加 `trigger`（不破坏老代码，但两字段语义重叠），还是直接把 `user_input` 换成 `trigger`（干净、单一事实源，但破坏调用链和持久化）。按 SSOT 倾向后者，落地时再拍。

<!-- 记录重要取舍及理由，作为后续变更的依据 -->

## 8. 版本里程碑

<!-- 版本、目标、时间点 -->

## 9. 术语表

### Provider

一份具名配置，写清楚 agent 调哪个模型、连哪个地址、用什么 key。

对 agent 只暴露一个方法 `complete()`：传入消息和工具，返回流式响应。agent 不关心底层是哪家厂商。

一个 Provider 由四部分组成：

- **kind**：接入点类型，决定内置地址和读取哪个环境变量。支持 8 种：`openai`、`deepseek`、`kimi`、`mimo`、`longcat`、`ollama`、`vllm`、`sglang`。
- **model**：模型 ID，例如 `deepseek-v4-flash`。
- **base_url**：服务地址。每种 kind 有内置默认值，可覆盖。
- **api_key**：凭据。留空时回退到该 kind 对应的环境变量。本地 kind（`ollama`、`vllm`、`sglang`）不需要。

配置里可以并存多个 Provider，每个有自己的名字：

```toml
[provider.deepseek]
kind = "deepseek"
model = "deepseek-v4-flash"
api_key = ""              # 留空回退 DEEPSEEK_API_KEY

[provider.local]
kind = "ollama"
model = "qwen3:8b"        # 本地模型，无需 api_key

[agent]
provider = "deepseek"     # 主 agent 用哪个
```

同一厂商的多个模型，就写成多个具名 Provider，`kind` 相同、`model` 不同，`api_key` 都留空共用一个环境变量：

```toml
[provider.deepseek_flash]
kind = "deepseek"
model = "deepseek-v4-flash"
api_key = ""              # 留空回退 DEEPSEEK_API_KEY

[provider.deepseek_pro]
kind = "deepseek"
model = "deepseek-v4-pro"
api_key = ""              # 同一个 key，不用重复填

[provider.deepseek_reasoner]
kind = "deepseek"
model = "deepseek-reasoner"

[agent]
provider = "deepseek_flash"   # 主 agent 默认用哪个
```

各 kind 的内置地址与环境变量：

| kind | 内置 base_url | 环境变量 | 需要 key |
|------|---------------|----------|----------|
| `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | 是 |
| `deepseek` | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | 是 |
| `kimi` | `https://api.moonshot.cn/v1` | `MOONSHOT_API_KEY` | 是 |
| `mimo` | `https://api.mimo-v2.com/v1` | `MIMO_API_KEY` | 是 |
| `longcat` | `https://api.longcat.chat/openai/v1` | `LONGCAT_API_KEY` | 是 |
| `ollama` | `http://127.0.0.1:11434/v1` | `OLLAMA_API_KEY` | 否 |
| `vllm` | `http://127.0.0.1:8000/v1` | `VLLM_API_KEY` | 否 |
| `sglang` | `http://127.0.0.1:30000/v1` | `SGLANG_API_KEY` | 否 |

要点：

- 同一厂商的多个模型写成多个具名 Provider，一份 Provider 配置对应一个可运行模型档案。
- 创建 Task 时，Provider 的名字、kind、model、base_url 会冻结进 `task.toml`；api_key 不落盘，始终从全局配置或环境变量现取。
- 配置两个及以上 Provider 时，Desktop、Web、VS Code 的聊天界面出现模型选择器，可在会话中途切换（见 model handoff）。
