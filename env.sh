#!/usr/bin/env bash
set -euo pipefail

# Load uv (adds ~/.local/bin to PATH)
source "$HOME/.local/bin/env"

# Ensure local SoX is available
export PATH="$HOME/.local/bin:$PATH"

# Activate project venv
source "$HOME/qwen3-tts/.venv/bin/activate"

# Prefer CUDA 12.8 toolkit for compatibility with torch+cu128
if [ -d "/usr/local/cuda-12.8" ]; then
  export CUDA_HOME="/usr/local/cuda-12.8"
else
  export CUDA_HOME="/usr/local/cuda"
fi
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
