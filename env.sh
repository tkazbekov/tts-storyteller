#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$HOME/.local/bin/env" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.local/bin/env"
fi

export PATH="$HOME/.local/bin:$PATH"

if [ -d "$SCRIPT_DIR/.venv" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.venv/bin/activate"
else
    echo "Warning: .venv not found. Run ./scripts/start.sh or uv venv -p 3.12 .venv" >&2
fi

export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

if [ -f "$SCRIPT_DIR/.env" ]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/.env"
  set +o allexport
fi

if [ -d "/usr/local/cuda-12.8" ]; then
  export CUDA_HOME="/usr/local/cuda-12.8"
elif [ -d "/usr/local/cuda" ]; then
  export CUDA_HOME="/usr/local/cuda"
fi

if [ -n "${CUDA_HOME:-}" ]; then
  export PATH="$CUDA_HOME/bin:$PATH"
  export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
fi
