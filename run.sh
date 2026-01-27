#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env.sh"

MODEL="${1:-Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice}"
IP="${IP:-0.0.0.0}"
PORT="${PORT:-8000}"

exec qwen-tts-demo "$MODEL" --ip "$IP" --port "$PORT"
