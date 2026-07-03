# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TTS Storyteller - a Python text-to-speech system built around pluggable TTS backends, currently Qwen3-TTS and VibeVoice, for multi-voice story generation. The core workflow is:
1. Design voices (VoiceDesign model) -> WAV files
2. Create reusable prompts (Base model) -> `.pt` files
3. Generate multi-voice stories (Base model) via API or CLI

## Commands

```bash
# Environment setup (always run first)
source env.sh

# Development
make install          # Install base dependencies (uv sync --no-dev; no torch)
make install-qwen     # Base + Qwen backend (torch/cu128 on Linux)
make install-all      # Base + all backends
make dev-install      # Install dev tools (ruff, mypy, pytest, pre-commit)
make lock-check       # Verify uv.lock matches pyproject.toml
make format           # Format code (ruff)
make lint             # Check code style
make lint-fix         # Auto-fix linting issues
make type-check       # Type check (mypy api lib)
make test             # Run tests (pytest)
make check            # Run all checks (lint + type-check + test)

# Running
make run-api          # Start FastAPI server (localhost:8000)

# Single test
source env.sh && pytest tests/test_basic.py -v
```

## Architecture

```
api/                  # FastAPI REST API
  app.py              # App setup with CORS + lifespan
  main.py             # Uvicorn entrypoint
  routes/             # Route handlers (stories, voices, pools, jobs, audio)

lib/                  # Reusable library modules
  paths.py            # Centralized path management
  models.py           # Pydantic models (Role, StoryLine, StoryTemplate, Job, etc.)
  validation.py       # Story template validation
  resolution.py       # Voice resolution: actorId -> casting -> defaultVoiceId
  generation.py       # TTS generation + audio concatenation
  database.py         # Async engine/session management (Postgres)
  repositories/       # DB-backed persistence for stories/voices/pools/jobs

services/             # API service layer
  jobs.py             # In-memory job queue + async processor
  story_generation.py # Story generation orchestration
  voice_generation.py # Voice generation orchestration

scripts/              # CLI tools
  voice_design.py     # Generate voices from VoiceDesign model
  create_prompts.py   # Create reusable .pt prompt files
  storyteller.py      # Generate story audio from JSON templates
  validate_story.py   # Validate story JSON
```

## Key Patterns

**Voice Resolution Priority:**
```
voiceId = line.actorId ?? casting[roleId] ?? defaultVoiceId
```

**Job System:** In-memory async queue with states: `queued` -> `running` -> `succeeded`/`failed`. Only terminal states are persisted to Postgres (job history); active jobs live in process memory.

**Storage:**
- Stories/voices/pools/jobs: Postgres via `lib/repositories/` (see `DATABASE_URL`)
- Prompts: `prompts/<backend>/<voice_id>.<ext>` (`.pt` for Qwen, `.json` for VibeVoice)
- Audio: `outputs/story/<story_id>/` (per-line WAVs + concatenated)
- `stories/` and `voices/` directories hold example/seed data for the CLIs only

**Model Loading:** TTS backends loaded once per process and cached (see `services/models.py` `ModelCache`)

## Environment

- Python 3.12 venv at `.venv` (created/managed by `uv sync`; lock in `uv.lock`)
- torch is NOT a base dependency — it installs only with the `qwen`/`vibevoice`
  extras (CUDA 12.8 cu128 wheels on Linux, PyPI wheels on macOS). The API and
  tests run torchless; backends import torch lazily inside their methods.
- FlashAttention comes from a prebuilt cu128/torch2.8/cp312 wheel (Linux x86_64 only)
- SoX binary required for audio concatenation (installed at `~/.local/bin/sox`)
- `env.sh` sets PYTHONPATH, activates venv, configures CUDA paths
