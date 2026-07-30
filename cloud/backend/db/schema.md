## 初始表结构

这版不做数据库 session。

鉴权直接走 JWT：

- 前端把 JWT 放在 `Authorization` header
- 后端验签
- 从 claims 里拿 `sub` 之类的用户字段
- 数据查询一律按当前用户过滤

所以首版重点不是“登录会话怎么存”，而是“多用户的 thread 怎么隔离地存”。

### 当前表

- `users`
- `user_passwords`
- `threads`
- `thread_messages`
- `thread_artifacts`

### 为什么这样定

`users`

- 只放用户基础信息

`user_passwords`

- 只放密码 hash
- 如果后面只保留外部登录，这张表也能删

演示种子见 [seed.sql](./seed.sql)（`admin@local` / 密码 `123`）。

### Compose

`cloud/docker-compose.yml` 会在 Postgres 首次启动时挂载：

1. `01_schema.sql` ← 本文件
2. `02_seed.sql` ← 演示账号

API 容器若发现缺表，也会再跑一遍 bootstrap（方便非 initdb 场景）。

对象存储：MinIO bucket 名默认 `pagent-artifacts`，对应 `thread_artifacts.storage_key`。

`threads`

- 云端会话主表
- 一条 thread 明确属于一个 `owner_user_id`
- 列表、详情、删除、恢复都先按这个用户边界过滤

`thread_messages`

- thread 下的消息
- 同时冗余存 `owner_user_id`
- 这样查用户自己的消息、做分区、做审计都更直接

`thread_artifacts`

- thread 产物索引
- 文件本体放对象存储
- 数据库只管归属、名字、类型、大小这些元数据

### 隔离规则

首版只做“用户私有 thread”，不做共享。

也就是：

- 一个 thread 只有一个 owner
- 所有消息和产物都跟着这个 owner
- 后端从 JWT claims 拿到用户 id 后，所有读写都强制带上 `owner_user_id = 当前用户`

这样不会和现在本地版的 `thread` 概念冲突太多，迁移也直接。

### 当前约定

- 数据库先按 PostgreSQL 设计
- `updated_at` 暂时由应用层维护
- JWT 默认无状态，不落库 session
- 线程状态、标题、消息数这些摘要字段收在 `threads`
- 消息正文保留 `content_text` 和 `content_json` 两个入口，方便兼容现在的消息模型

### 现在先不定的内容

- 刷新 token 黑名单
- 多设备登录管理
- thread 共享 / 协作
- workspace / project
- 审计日志
- 配额 / 计费

如果后面要做“团队共享 thread”，再单独补一张成员表，不需要推翻这版主干。
