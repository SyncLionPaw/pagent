## Backend

FastAPI 云端 API。

### 职责

- JWT 鉴权（环境变量 `CLOUD_JWT_SECRET`）
- 用户 / thread 持久化（PostgreSQL）
- Artifact 对象存储（S3 / MinIO）
- Wire：`POST /command` + `GET /events`
- 模型服务配置（`CLOUD_LLM_API_KEY` / `CLOUD_LLM_MODEL` / `CLOUD_LLM_BASE_URL`）

Cloud API 只读取部署环境中的配置，不读取宿主机的 `~/.pagent`。

### 关键文件

| 文件 | 说明 |
|------|------|
| `settings.py` | 环境变量 |
| `db.py` | Postgres 连接 / bootstrap |
| `storage.py` | MinIO / S3 |
| `db/schema.sql` | 表结构 |
| `db/seed.sql` | 演示账号 |
| `Dockerfile` | API 镜像 |
| `requirements.txt` | 镜像依赖 |

### 关键接口

- `GET /api/health` — 进程存活 + db/storage 明细
- `GET /api/ready` — 依赖就绪（compose healthcheck 用）

设计稿：

- [db/schema.md](./db/schema.md)
- [api/threads.md](./api/threads.md)
