# Web：对标 Desktop 的 React 工作台

Language: [中文](/zh/web) | English

**pagent Web** is a React SPA that mirrors **pagent Desktop**: same three-pane workbench (sessions / chat / project·sandbox·log), same Wire command & event JSON, talking to `pagent --http`.

::: tip Same protocol as Desktop HTTP mode
Desktop already supports `PAGENT_TRANSPORT=http`. Web uses that same backend: `POST /command` + `GET /events` (SSE), plus host helpers under `/api/*` (project tree, artifacts, …) that Electron used to do in the main process.
:::

## Run (dev)

```bash
# terminal 1 — backend
uv sync --group dev
uv run pagent --http --host 127.0.0.1 --port 8848

# terminal 2 — Vite
cd editors/web
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/command`, `/events`, and `/api` to port 8848.

## Run (single origin)

```bash
cd editors/web && npm install && npm run build
uv run pagent --http --host 127.0.0.1 --port 8848
```

When `editors/web/dist/index.html` exists, the HTTP server serves the SPA. Override with `PAGENT_WEB_DIST=/path/to/dist`.

Optional auth: `PAGENT_SERVER_TOKEN=secret` — browser stores the token in `localStorage` (`pagent-web-server-token`) and sends `Authorization: Bearer …`.

## What matches Desktop

| Area | Web |
|------|-----|
| Chat streaming, tools, reasoning, permits | Same `ChatRenderer` as Desktop / VS Code |
| Sessions / resume / reset / delete | Wire commands |
| Sandbox tree & status | Wire `sandbox_tree` / `sandbox_status` |
| Project tree & artifacts | `GET /api/project-*`, `/api/artifacts*` |
| YOLO | Client auto-`permit` (no process restart) |
| Onboarding / provider | Wire `set_provider` + `environment_check` |

## Single-user model

`pagent --http` remains **one process · one session · one runner**. The Web UI is a browser shell for that pod — not a multi-tenant SaaS.

Source: [editors/web/](https://github.com/SyncLionPaw/pagent/tree/main/editors/web)
