#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND="${TTS_START_BACKEND:-qwen}"
DOWNLOAD_MODELS=1
START_DB=1
RUN_MIGRATIONS=1
HOST="${TTS_HOST:-0.0.0.0}"
PORT="${TTS_PORT:-8000}"

usage() {
  cat <<USAGE
Usage: ./scripts/start.sh [options]

Options:
  --backend qwen|vibevoice|all   Backend dependencies and models to install/download (default: qwen)
  --skip-model-download          Do not pre-download Hugging Face models
  --no-db                        Do not start Docker Compose Postgres
  --no-migrations                Do not run Alembic/migration step
  --host HOST                    API host (default: 0.0.0.0)
  --port PORT                    API port (default: 8000)
  -h, --help                     Show this help
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --backend) BACKEND="${2:?missing backend}"; shift 2 ;;
    --skip-model-download) DOWNLOAD_MODELS=0; shift ;;
    --no-db) START_DB=0; shift ;;
    --no-migrations) RUN_MIGRATIONS=0; shift ;;
    --host) HOST="${2:?missing host}"; shift 2 ;;
    --port) PORT="${2:?missing port}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

case "$BACKEND" in
  qwen|vibevoice|all) ;;
  *) echo "Invalid backend '$BACKEND'. Use qwen, vibevoice, or all." >&2; exit 2 ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing it into ~/.local/bin"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -d .venv ]; then
  uv venv -p 3.12 .venv
fi

if [ ! -f .env ]; then
  cp .env.example .env
fi

# shellcheck disable=SC1091
source env.sh

# --frozen: install exactly what uv.lock records, never re-resolve on deploy.
SYNC_ARGS=(--frozen --no-dev)
case "$BACKEND" in
  qwen)      SYNC_ARGS+=(--extra qwen) ;;
  vibevoice) SYNC_ARGS+=(--extra vibevoice) ;;
  all)       SYNC_ARGS+=(--extra qwen --extra vibevoice) ;;
esac
uv sync "${SYNC_ARGS[@]}"

if [ "$START_DB" = 1 ] && command -v docker >/dev/null 2>&1; then
  docker compose up -d db
fi

if [ "$RUN_MIGRATIONS" = 1 ]; then
  alembic upgrade head
fi

if [ "$DOWNLOAD_MODELS" = 1 ]; then
  python scripts/download_models.py --backend "$BACKEND"
fi

export TTS_HOST="$HOST"
export TTS_PORT="$PORT"
exec python api/main.py
