# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Qwen3-TTS Local Playground - a Python text-to-speech system built around Alibaba's Qwen3-TTS models for multi-voice story generation. The core workflow is:
1. Design voices (VoiceDesign model) -> WAV files
2. Create reusable prompts (Base model) -> `.pt` files
3. Generate multi-voice stories (Base model) via API or CLI

## Commands

```bash
# Environment setup (always run first)
source env.sh

# Development
make install          # Install production dependencies
make dev-install      # Install dev tools (ruff, mypy, pytest, pre-commit)
make format           # Format code (ruff)
make lint             # Check code style
make lint-fix         # Auto-fix linting issues
make type-check       # Type check (mypy api lib)
make test             # Run tests (pytest)
make check            # Run all checks (lint + type-check + test)

# Running
make run-api          # Start FastAPI server (localhost:8000)
make run-demo         # Start Gradio demo

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
  storage.py          # File-based storage for stories/voices

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

**Job System:** Async in-memory queue with states: `queued` -> `running` -> `succeeded`/`failed`

**Storage:**
- Stories: `stories/<story_id>.json`
- Prompts: `prompts/<voice_id>.pt` (PyTorch serialized)
- Audio: `outputs/story/<story_id>/` (per-line WAVs + concatenated)

**Model Loading:** TTS model loaded once per process and cached (see `lib/runtime.py`)

## Environment

- Python 3.12 venv at `.venv`
- CUDA 12.8 + torch 2.8.0+cu128 + FlashAttention 2.8.3
- SoX required for audio concatenation (installed at `~/.local/bin/sox`)
- `env.sh` sets PYTHONPATH, activates venv, configures CUDA paths
