## Frontend

React 云端前端：登录墙 + 挂载 `editors/web`。

### 开发

```bash
cd cloud/frontend
npm install
npm run dev
```

默认 http://127.0.0.1:5174 ，Vite 把 `/api` `/events` `/command` 代理到 `:8787`。

演示账户：`admin` / `123`

### 生产镜像

多阶段构建：`npm run build` → nginx 托管静态资源，并反代 API。

```bash
# 仓库根目录
docker build -f cloud/frontend/Dockerfile -t pagent-cloud-web .
```

`nginx.conf` 把 `/api` `/command` `/events` 转到 compose 服务 `api:8787`。
