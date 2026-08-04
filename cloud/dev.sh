#!/usr/bin/env bash
# pagent Cloud 一键本地开发脚本。
#
# 拉起三块：基础服务(compose: postgres/redis/minio) + 后端(uvicorn) + 前端(vite)。
# 后端必须在仓库根运行，否则 `import cloud` 会 ModuleNotFoundError。
#
# 用法（在任意目录）：
#   ./cloud/dev.sh          启动全部
#   ./cloud/dev.sh backend  只启动后端
#   ./cloud/dev.sh deps      只启动基础服务
#   ./cloud/dev.sh down      停止基础服务（保留数据卷）
#
# Ctrl+C 会一并停掉后端和前端；基础服务留在后台，用 `down` 显式停。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLOUD="$ROOT/cloud"
ENV_FILE="$CLOUD/.env"
COMPOSE_FILE="$CLOUD/docker-compose.yml"

BACKEND_PORT=8787
FRONTEND_PORT=5174

log() { printf '\033[1;36m[dev]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[dev] %s\033[0m\n' "$*" >&2; exit 1; }

# 清掉占用端口的残留进程，避免 "address already in use" 或连到旧进程。
free_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti :"$port" 2>/dev/null || true)"
  [[ -z "$pids" ]] && return
  log "端口 $port 被占用，清理进程：$pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 1
  pids="$(lsof -ti :"$port" 2>/dev/null || true)"
  # shellcheck disable=SC2086
  [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
}

# 轮询后端 health，通了才返回。
wait_backend() {
  log "等待后端 :$BACKEND_PORT 就绪"
  for _ in $(seq 1 40); do
    if curl -s -m 2 -o /dev/null "http://127.0.0.1:$BACKEND_PORT/api/health"; then
      log "后端就绪"
      return 0
    fi
    sleep 1
  done
  die "后端等待超时，检查上方日志"
}

# 探测容器运行时：优先 docker，退回 podman。
detect_compose() {
  if command -v docker >/dev/null 2>&1 && docker version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
    return
  fi
  if command -v podman >/dev/null 2>&1; then
    COMPOSE=(podman compose)
    return
  fi
  die "没有可用的 docker 或 podman，无法启动基础服务"
}

ensure_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    log "未找到 cloud/.env，从 .env.example 复制"
    cp "$CLOUD/.env.example" "$ENV_FILE"
    log "已生成 cloud/.env，请填入 CLOUD_LLM_API_KEY 后重跑"
  fi
}

deps_up() {
  detect_compose
  log "启动基础服务 (${COMPOSE[*]})"
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
  log "等待 PostgreSQL 就绪"
  for _ in $(seq 1 30); do
    if "${COMPOSE[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
        exec -T postgres pg_isready -U pagent -d pagent >/dev/null 2>&1; then
      log "PostgreSQL 就绪"
      return
    fi
    sleep 1
  done
  die "PostgreSQL 等待超时，检查 compose 日志"
}

deps_down() {
  detect_compose
  log "停止基础服务（保留数据卷）"
  "${COMPOSE[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
}

# 把 cloud/.env 的变量导出给后端进程；后端用 os.environ 直接读，不会自动加载 .env。
load_env() {
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  [[ -n "${CLOUD_LLM_API_KEY:-}" ]] || log "警告：CLOUD_LLM_API_KEY 为空，对话会失败"
}

backend_up() {
  ensure_env
  load_env
  free_port "$BACKEND_PORT"
  log "启动后端 uvicorn :${BACKEND_PORT}（工作目录=仓库根）"
  cd "$ROOT"
  uv run --group dev --group cloud \
    uvicorn cloud.backend.app:app --reload --port "$BACKEND_PORT"
}

frontend_up() {
  free_port "$FRONTEND_PORT"
  cd "$CLOUD/frontend"
  if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/.nvm/nvm.sh"
    nvm use >/dev/null 2>&1 || nvm use 22 >/dev/null 2>&1 || true
  fi
  [[ -d node_modules ]] || { log "安装前端依赖"; npm install; }
  log "启动前端 vite :$FRONTEND_PORT"
  npm run dev
}

run_all() {
  ensure_env
  deps_up
  # 先串行清掉两个端口的残留，避免 wait_backend 误连到旧僵尸后端。
  free_port "$BACKEND_PORT"
  free_port "$FRONTEND_PORT"
  # 后端先起并等它 health 通过，再起前端，避免前端先连报 ECONNREFUSED。
  ( backend_up ) &
  BACKEND_PID=$!
  trap 'log "收到中断，停止后端/前端"; kill "$BACKEND_PID" "${FRONTEND_PID:-}" 2>/dev/null || true' INT TERM
  wait_backend
  ( frontend_up ) &
  FRONTEND_PID=$!
  log "后端 http://127.0.0.1:$BACKEND_PORT  前端 http://127.0.0.1:$FRONTEND_PORT  登录 admin/123"
  wait
}

case "${1:-all}" in
  all) run_all ;;
  deps) ensure_env; deps_up ;;
  backend) backend_up ;;
  frontend) frontend_up ;;
  down) deps_down ;;
  *) die "未知参数：$1（可用 all|deps|backend|frontend|down）" ;;
esac
