# pagent Web Workbench

React Web UI for `pagent --http`, visually aligned with the Electron desktop workbench.

## Development

```bash
# terminal 1
uv run pagent --http --host 127.0.0.1 --port 8848

# terminal 2
cd editors/web
npm install
npm run dev
```

The Vite dev server proxies `/command`, `/events`, and `/api/*` to
`http://127.0.0.1:8848`.

## Production

```bash
cd editors/web
npm run build
uv run pagent --http --host 127.0.0.1 --port 8848
```

When `dist/` exists, `pagent --http` serves the built Web UI from the same origin.
