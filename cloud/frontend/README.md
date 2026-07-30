## Frontend

这里放云端前端代码。

当前选型：React，尽量和 `editors/web` 保持一致。

预期职责：

- 登录态
- 用户侧页面
- 面向云端 API 的前端实现

当前第一步已经落地：

- 登录墙
- 固定演示账户：`admin`
- 固定演示密码：`123`

启动方式：

```bash
cd /Users/bytedance/docs/pagent
uv run --with fastapi --with uvicorn uvicorn cloud.backend.app:app --reload --port 8787
```

```bash
cd /Users/bytedance/docs/pagent/cloud/frontend
npm install
npm run dev
```

然后打开：

`http://127.0.0.1:5174`
