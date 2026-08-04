# Cloud 本地开发

## 一键启动

在仓库根目录执行：

```bash
./cloud/dev.sh
```

它会依次拉起基础服务（PostgreSQL / Redis / MinIO）、后端（uvicorn :8787）和前端（vite :5174），并在结束时（Ctrl+C）一并停掉后端和前端。首次运行会自动从 `.env.example` 生成 `cloud/.env`，填入 `CLOUD_LLM_API_KEY` 后重跑即可。

打开 `http://127.0.0.1:5174`，演示登录账号为 `admin` / `123`。

子命令：

```bash
./cloud/dev.sh deps      # 只起基础服务
./cloud/dev.sh backend   # 只起后端（在仓库根运行，避免 ModuleNotFoundError）
./cloud/dev.sh frontend  # 只起前端
./cloud/dev.sh down      # 停基础服务，保留数据卷
```

后端必须在**仓库根**运行。在 `cloud/` 目录里跑 `uvicorn cloud.backend.app:app` 会报 `ModuleNotFoundError: No module named 'cloud'`，因为 `cloud` 包的父目录（仓库根）才在 `sys.path` 上。

---

## 手动分步启动

`docker-compose.yml` 只启动本地开发依赖：

| 服务 | 用途 | 默认地址 |
|---|---|---|
| PostgreSQL 16 | 用户、thread、消息和 artifact 索引 | `127.0.0.1:5432` |
| Redis 7.4 | 缓存、分布式锁和事件分发 | `127.0.0.1:6379` |
| MinIO | S3 兼容的 artifact 对象存储 | API `127.0.0.1:9000`，控制台 `127.0.0.1:9001` |

前端和后端在宿主机中分别启动，修改代码后无需重新构建容器。

## 准备配置

在仓库根目录执行：

```bash
cp cloud/.env.example cloud/.env
```

默认开发账号：

- PostgreSQL：`pagent` / `pagent`，数据库名 `pagent`
- Redis 密码：`pagentredis`
- MinIO：`pagent` / `pagentminio`

如本机端口冲突，可在 `cloud/.env` 中修改对应的 `*_PORT`。

## 启动基础服务

```bash
docker compose -f cloud/docker-compose.yml --env-file cloud/.env up -d
```

查看状态和日志：

```bash
docker compose -f cloud/docker-compose.yml --env-file cloud/.env ps
docker compose -f cloud/docker-compose.yml --env-file cloud/.env logs -f
```

所有服务显示 `healthy` 后即可启动 Cloud API 和前端。

## 启动项目代码

后端：

```bash
CLOUD_LLM_API_KEY=your-api-key \
uv run --group dev --group cloud \
  uvicorn cloud.backend.app:app --reload --port 8787
```

前端：

```bash
cd cloud/frontend
nvm use
npm install
npm run dev
```

打开 `http://127.0.0.1:5174`，演示登录账号为 `admin` / `123`。

## 停止基础服务

停止并删除容器和网络，具名数据卷会继续保留：

```bash
docker compose -f cloud/docker-compose.yml --env-file cloud/.env down
```

需要同时清空 PostgreSQL、Redis 和 MinIO 数据时执行：

```bash
docker compose -f cloud/docker-compose.yml --env-file cloud/.env down -v
```

`down -v` 会永久删除本地开发数据。
