## Cloud

云端版本：用户系统 + 前后端分离，与本地 `editors/*` / `src/app/*` 解耦。

选型：FastAPI · React（复用 `editors/web`）· PostgreSQL · MinIO（S3）

计划书 → [PLAN.md](./PLAN.md)

### 目录

| 路径 | 作用 |
|------|------|
| `frontend/` | 登录壳 + Web 工作台 |
| `backend/` | Cloud API |
| `docker-compose.yml` | db + minio + api + web |
| `.env.example` | 环境变量模板 |

### 一键起全套（推荐）

在**仓库根目录**：

```bash
cp cloud/.env.example cloud/.env
# 在 cloud/.env 中填写 CLOUD_LLM_API_KEY
docker compose -f cloud/docker-compose.yml --env-file cloud/.env up --build
```

然后打开：

- Web：http://127.0.0.1:8080
- API：http://127.0.0.1:8787/api/health
- MinIO Console：http://127.0.0.1:9001 （`pagent` / `pagentminio`）
- Postgres：`localhost:5432` （`pagent` / `pagent` / db=`pagent`）

演示登录：`admin` / `123`（已写入 `backend/db/seed.sql`）

### 组件说明

- **PostgreSQL**：启动时执行 `schema.sql` + `seed.sql`；API 也会在缺表时 bootstrap
- **MinIO**：`minio-init` 创建 bucket `pagent-artifacts`
- **runtime_data volume**：保存 per-thread 运行时目录（`CLOUD_RUNTIME_ROOT`）；长期对话数据由 PostgreSQL 管理

### 本地开发（不经过 compose）

```bash
# 终端 1 — 至少要有可连的 Postgres / MinIO，或接受 /api/ready=503
CLOUD_LLM_API_KEY=your-api-key \
uv run --with fastapi --with 'uvicorn[standard]' --with 'psycopg[binary]' --with boto3 --with argon2-cffi \
  uvicorn cloud.backend.app:app --reload --port 8787

# 终端 2
cd cloud/frontend && npm install && npm run dev
```

打开 http://127.0.0.1:5174
