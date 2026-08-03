## Cloud

云端版本：用户系统 + 前后端分离，与本地 `editors/*` / `src/app/*` 解耦。

选型：FastAPI · React（复用 `editors/web`）· PostgreSQL · MinIO（S3）

计划书 → [PLAN.md](./PLAN.md)

### 目录

| 路径 | 作用 |
|------|------|
| `frontend/` | 登录壳 + Web 工作台 |
| `backend/` | Cloud API |
| `docker-compose.yml` | 本地开发依赖：PostgreSQL + Redis + MinIO |
| `.env.example` | 基础服务环境变量模板 |
| `DEVELOPMENT.md` | 本地开发与启停说明 |

### 本地开发

Compose 只启动第三方基础服务，不构建或运行项目代码：

```bash
cp cloud/.env.example cloud/.env
docker compose -f cloud/docker-compose.yml --env-file cloud/.env up -d
```

API、前端及基础服务的完整启动和停止方式见
[Cloud 本地开发](./DEVELOPMENT.md)。

生产环境分别部署 API 与 Web，并使用平台提供的 PostgreSQL、Redis、S3、密钥、
网络和持久化存储。
