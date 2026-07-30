# pagent cloud frontend (static SPA + nginx reverse proxy)
# build from repo root:
#   docker build -f cloud/frontend/Dockerfile -t pagent-cloud-web .

FROM node:22-bookworm-slim AS build

WORKDIR /src

COPY cloud/frontend/package.json cloud/frontend/package-lock.json /src/cloud/frontend/
WORKDIR /src/cloud/frontend
RUN npm ci --registry https://registry.npmjs.org/

# cloud frontend imports editors/web (+ vscode webview helpers)
COPY editors/web /src/editors/web
COPY editors/vscode/src/webview /src/editors/vscode/src/webview
COPY cloud/frontend /src/cloud/frontend

RUN npm run build

FROM nginx:1.27-alpine

COPY cloud/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/cloud/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
