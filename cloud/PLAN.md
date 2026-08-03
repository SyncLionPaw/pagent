# pagent Cloud 计划书

**状态**: 登录、工作台、本地联调环境和真实 Runner 已接通；Thread 持久化与云端沙箱尚未接线。
**对象**: 最新云端版本（`cloud/`）后续要做什么、按什么顺序做。  
**配套**: [README.md](./README.md) · [backend/db/schema.md](./backend/db/schema.md) · [backend/api/threads.md](./backend/api/threads.md) · 本地 Web 基座见 [docs/web.md](../docs/web.md)

---

## 1. 产品定位

Cloud 面向远程部署，为多个用户提供相互隔离的科研工作台。

| 形态 | 说明 |
|------|------|
| **前端** | React 壳：登录墙 + 复用 `editors/web` 工作台（含已合入的 mobile 布局） |
| **协议** | 与 Desktop / Web 同一套：`POST /command` + `GET /events`（SSE / Wire） |
| **后端** | FastAPI：用户鉴权、thread 隔离、再把请求接到真实 Runner |
| **部署演进** | 单实例云端 → 多实例调度；本地启动仅用于开发与测试 |

**一句话**: 浏览器薄客户端连接远端 Python runtime；每个 thread 拥有独立的持久化记录与沙箱。

---

## 2. 现状盘点（已有 / 缺口）

### 已落地

- **目录骨架**: `cloud/frontend` + `cloud/backend`，与本地 `editors/*` / `src/app/*` 解耦
- **鉴权演示**: 固定 `admin/123` → JWT（`Authorization: Bearer`）→ `/api/auth/me`
- **登录 UI**: drawer 登录墙、登出挂到工作台 footer
- **工作台挂载**: 登录后直接渲染 `editors/web` App；token 写入 Web bridge 使用的 localStorage
- **Agent 通路**: `/events` SSE、`/command` 已接入 `pagentv4` Runner
- **数据设计稿**: PostgreSQL schema（users / threads / messages / artifacts）+ Thread REST 草图
- **本地联调环境**: `docker-compose.yml` 只启动 PostgreSQL、Redis 和 MinIO
- **本地基座（已合 main）**: Web Desktop 对标（PR #3）+ mobile 抽屉布局（PR #4）

### 明确缺口

| 缺口 | 现状 |
|------|------|
| Runner 生命周期 | 当前按用户缓存在单个 API 进程中，尚未按 thread 调度 |
| Thread 持久化 | 内存 dict；schema.sql 未接线 |
| 注册 / 多用户 | 仅演示账号；无密码表读写 |
| Sandbox | 假 status / 空 tree；无 per-user workspace |
| Artifact / 项目树 | API 返回空或 404 |
| 对象存储 | `thread_artifacts.storage_key` 有设计无实现 |
| 生产密钥 | JWT secret 写死；无 refresh / 登出吊销 |
| 多实例事件分发 | SSE 订阅只在单个 API 进程内，尚未接入 Redis / NATS |

---

## 3. 原则（后续都按这个拍板）

1. **UI 不重写**: Cloud 前端继续包 `editors/web`；云差异（登录、登出、多用户壳）放在 `cloud/frontend`。
2. **协议不另起炉灶**: 命令与事件继续走 Wire；REST 只补「用户 / thread 元数据 / artifact 索引」这类宿主能力。
3. **隔离写死在服务端**: JWT → `owner_user_id`；客户端永不传 owner；thread / message / artifact 查询一律带用户过滤（见 schema 约定）。
4. **隔离从第一版生效**: Runner、thread、workspace 和 artifact 都以 `user_id + thread_id` 为边界；共享调度、配额、计费后置。
5. **Runtime 稳了再加产品花活**: cancel / permit / 断线恢复优先于插件市场、会话树、计费面板。
6. **不做的事（本阶段）**: 原生 iOS App、设备上跑 Python、thread 协作共享、MCP 宿主、计费。

---

## 4. 分期路线

### Phase 0 — 演示闭环（当前 → 马上）

**目标**: 登录后能够通过远端 Runner 完成一轮流式对话。

| # | 事项 | 验收 |
|---|------|------|
| 0.1 | Cloud `/command` + `/events` 接到真实 `pagentv4` Runner（可先单进程、单活跃 thread） | 登录 → 发消息 → 流式 Wire 事件与本地 Web 一致 |
| 0.2 | `cancel` / `permit` / `deny` 打通 | 工具审批与取消行为与 `pagent --http` 一致 |
| 0.3 | 环境变量化 JWT secret、CORS、演示开关 | 去掉硬编码生产密钥；文档写清本地启动 |
| 0.4 | 统一启动脚本（backend + frontend） | README 一条命令可起演示 |

**实现倾向**: 优先 **复用** `pagent --http` 的 bridge/runner 装配，Cloud 层只加 JWT 用户上下文；避免再写第二套事件循环。

---

### Phase 1 — 用户私有 Thread 持久化

**目标**: 刷新页面 / 重登后会话还在；用户之间看不见对方 thread。

| # | 事项 | 验收 |
|---|------|------|
| 1.1 | 接入 PostgreSQL（或先 SQLite 开发、schema 对齐） | `schema.sql` 可迁移上线 |
| 1.2 | 落地 Thread API：`POST/GET /api/threads`、`POST .../messages` | 与 [api/threads.md](./backend/api/threads.md) 一致；强制 owner 过滤 |
| 1.3 | `list_threads` / `resume` / `delete_thread` / `reset` 读写库 | Web 左侧会话列表来自 DB，不是内存 |
| 1.4 | 消息写入 `thread_messages`；摘要回写 `threads.message_count` / `last_message_at` | HistoryReplay 与 DB 一致 |
| 1.5 | 真实用户表 + 密码 hash（argon2id）；可保留演示账号种子 | 不再写死唯一 admin（或仅 `CLOUD_DEMO=1`） |

---

### Phase 2 — 工作区与产物

**目标**: 云端会话有可隔离的工作目录与可下载产物。

| # | 事项 | 验收 |
|---|------|------|
| 2.1 | Sandbox worker 为每个 user / thread 创建独立 workspace | workspace 生命周期与 thread 绑定 |
| 2.2 | 使用隔离容器执行代码和命令 | `sandbox_status` / `sandbox_tree` 有真数据 |
| 2.3 | Artifact 落 S3 + `thread_artifacts` 索引 | `/api/artifacts*` 可读可列 |
| 2.4 | `/api/project-tree` / `project-files` 读用户工作区 | 右侧工程树可用 |

---

### Phase 3 — 生产部署

**目标**: 在服务器或集群中稳定部署完整 Cloud 服务。

| # | 事项 | 验收 |
|---|------|------|
| 3.1 | API / Web 生产镜像与平台部署清单 | 可连接托管 PostgreSQL、S3 和密钥服务 |
| 3.2 | HTTPS / 反向代理说明；SSE 长连接与超时 | 手机浏览器可稳定用 |
| 3.3 | Token TTL、可选 refresh；登出可废弃（短期可用版本号/黑名单） | 基本会话安全 |
| 3.4 | 健康检查、结构化日志、基础限流 | 满足生产运行要求 |

---

### Phase 4 — 官方多租户（后置）

仅在 Phase 0–3 稳定后再开：

- 一控制面调度多 runner（队列 / 租约）
- 配额、用量、计费
- OAuth / SSO、邮箱验证
- Thread 共享 / 团队空间（单独成员表，不推翻现有 owner 模型）
- 审计日志、管理员后台

**本阶段不做原生 App**；手机继续用 Web（已有 mobile 布局），需要「加到主屏」时再考虑 PWA / Capacitor 壳。

---

## 5. 与本地产品线的关系

```text
editors/web  ──────────────►  同一套 UI / Wire 客户端
     ▲                              ▲
     │                              │
pagent --http（单用户本机）    cloud/backend（JWT + 多用户隔离 + 持久化）
     │                              │
     └──────── pagentv4 Runner ─────┘
```

- **本地 Web / Desktop**: 继续服务「本机一个 runner」。
- **Cloud**: 同一 UI，多一层用户与存储；runner 由服务端按用户/thread 拉起。
- **Runtime 夯实**（inbound / cancel / permit 等）见 [docs/pagentv4/hardening-plan.md](../docs/pagentv4/hardening-plan.md)；Cloud 依赖这些契约，但不在 Cloud 目录里重做一遍。

---

## 6. 建议的近期迭代顺序（可直接拆 issue）

1. **P0 接通 Runner** — 去掉「还没接入真实 agent」的 Error，形成可演示云端聊天  
2. **P0 启动与密钥** — 可分享的本地 Cloud demo 文档  
3. **P1 DB + Thread API** — 会话列表持久化与用户隔离  
4. **P1 resume / HistoryReplay** — 刷新不丢上下文  
5. **P2 workspace + sandbox** — 真正能改文件、跑命令  
6. **P2 artifacts** — 产物可下载  
7. **P3 生产部署** — API / Web 镜像、托管依赖与平台部署清单

每完成一档，更新本文件「现状盘点」与 `cloud/*/README.md`。

---

## 7. 成功标准（第一版 Cloud 可对外说「能用」）

- [ ] 用户注册或种子账号登录后进入与本地一致的工作台  
- [ ] 能创建 / 列出 / 恢复 / 删除自己的 thread，看不到他人数据  
- [ ] 一轮带工具调用的对话可流式完成，支持取消与工具审批  
- [ ] 工作区文件与 artifact 按 thread 隔离可见  
- [ ] 可通过目标云平台的部署清单发布，并接入托管 PostgreSQL、S3 与密钥服务

未满足前，对外口径保持：**Cloud 演示 / 预览**。
