# Web：对标桌面端的 React 工作台

语言：中文 | [English](/web)

**pagent Web** 是用 React 做的 SPA，界面与能力对齐 **pagent Desktop**：三栏工作台（会话 / 对话 / 项目·沙箱·日志），命令与事件 JSON 与 Desktop 一致，后端接 `pagent --http`。

::: tip 与 Desktop 的 HTTP 模式同一套后端
Desktop 已支持 `PAGENT_TRANSPORT=http`。Web 用的就是这个后端：`POST /command` + `GET /events`（SSE），再加上 `/api/*` 宿主接口（项目树、产物预览等——桌面端原先在 Electron 主进程里做）。
:::

## 开发

```bash
# 终端 1 — 后端
uv sync --group dev
uv run pagent --http --host 127.0.0.1 --port 8848

# 终端 2 — Vite
cd editors/web
npm install
npm run dev
```

打开 **http://127.0.0.1:5173**。Vite 会把 `/command`、`/events`、`/api` 代理到 8848。

## 同域部署

```bash
cd editors/web && npm install && npm run build
uv run pagent --http --host 127.0.0.1 --port 8848
```

存在 `editors/web/dist/index.html` 时，HTTP 服务会直接托管 SPA。可用 `PAGENT_WEB_DIST` 指定目录。

可选鉴权：`PAGENT_SERVER_TOKEN=secret`；浏览器把 token 存在 `localStorage`（`pagent-web-server-token`），请求时带 `Authorization: Bearer …`。

## 与桌面端的对应

| 能力 | Web |
|------|-----|
| 流式对话、工具卡、思考、审批 | 复用与 Desktop / VS Code 相同的 `ChatRenderer` |
| 会话列表 / 恢复 / 新建 / 删除 | Wire 命令 |
| 沙箱树与状态 | `sandbox_tree` / `sandbox_status` |
| 项目树与产物 | `/api/project-*`、`/api/artifacts*` |
| YOLO | 前端自动 `permit`（无需重启进程） |
| 首次设置 / 写 Key | `set_provider` + `environment_check` |

## 单用户

`pagent --http` 仍是 **单进程 · 单会话 · 单 runner**。Web 只是这个进程的浏览器壳，不是多租户服务。

源码：[editors/web/](https://github.com/SyncLionPaw/pagent/tree/main/editors/web)
