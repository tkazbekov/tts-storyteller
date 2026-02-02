#!/usr/bin/env bash
set -euo pipefail

# Get the directory where this script is located (project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load uv (adds ~/.local/bin to PATH) - optional
if [ -f "$HOME/.local/bin/env" ]; then
    source "$HOME/.local/bin/env"
fi

# Ensure local SoX is available
export PATH="$HOME/.local/bin:$PATH"

# Activate project venv
source "$SCRIPT_DIR/.venv/bin/activate"

# Add project root to PYTHONPATH so imports work
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

# Load repository .env if present so shell commands get the same vars
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/.env"
  set +o allexport
fi

# Prefer CUDA 12.8 toolkit for compatibility with torch+cu128
if [ -d "/usr/local/cuda-12.8" ]; then
  export CUDA_HOME="/usr/local/cuda-12.8"
else
  export CUDA_HOME="/usr/local/cuda"
fi
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
