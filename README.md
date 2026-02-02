# Qwen3-TTS Local Playground

This folder is a minimal, reproducible setup for Qwen3-TTS with:
- UV for Python venv and package management (faster than pip)
- CUDA + FlashAttention
- Scripts to design voices and reuse them for storytelling
- FastAPI backend for story management and generation


This repo is meant as a small, explicit pipeline you can rerun and tweak. The core flow is:
1) design voices (VoiceDesign model)
2) turn those voices into prompt files (Base model)
3) generate a multi-voice story (Base model) via API or CLI

## What is installed

- Python 3.12 venv at `~/qwen3-tts/.venv`
- PyTorch pinned to a FlashAttention-compatible combo:
  - torch 2.8.0+cu128
  - torchaudio 2.8.0+cu128
  - torchvision 0.23.0+cu128
- FlashAttention 2.8.3 (prebuilt wheel)
- qwen-tts
- SoX built locally at `~/.local/bin/sox`

## Quick start

### Development setup

```bash
cd ~/qwen3-tts
source env.sh

# Install dependencies
make install

# Install dev tools (linting, formatting, testing)
make dev-install
```

### Run the API server

```bash
make run-api
# or
source env.sh && python api/main.py
```

Then open:
```
http://localhost:8000/docs  # Interactive API docs
http://localhost:8000        # API root
```

### Run the Gradio demo

```bash
make run-demo
# or
./run.sh
```

`run.sh` uses the `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` model by default and starts
`qwen-tts-demo` on `0.0.0.0:8000`. You can override:

```bash
IP=127.0.0.1 PORT=8001 ./run.sh
./run.sh Qwen/Qwen3-TTS-12Hz-1.7B-Base
```

## Development workflow

### Code quality tools

```bash
make format      # Format code (like Prettier)
make lint        # Lint code (like ESLint)
make type-check  # Type check (like TypeScript)
make test        # Run tests
make check       # Run all checks
make clean       # Clean cache files
```

See `make help` for all available commands.

### Project structure

```
qwen3-tts/
  api/              # FastAPI application
    app.py          # FastAPI app setup
    main.py         # API entrypoint
    routes/         # API route modules
  services/         # API service layer
  lib/              # Reusable library modules
    paths.py        # Path utilities
    models.py       # Pydantic models
    validation.py   # Story validation
    resolution.py   # Role-to-voice resolution
    generation.py   # TTS generation logic
    storage.py      # File storage utilities
  scripts/          # CLI tools
    voice_design.py
    create_prompts.py
    storyteller.py  # JSON story generation
    validate_story.py
    common.py
  stories/          # Story templates (JSON only)
  voices/           # Voice definitions
  prompts/          # Voice prompt files (.pt)
  outputs/          # Generated audio
  tests/            # Test files
```

## Voice design + reuse workflow

You will do this in three steps:

1) **Design voices** (VoiceDesign model) -> WAV files
2) **Create prompts** (Base model) -> prompt `.pt` files
3) **Generate story** (Base model) using those prompts

### 1) Design voices

Edit `voices/voices.json` to describe the characters.

Then run:

```bash
cd ~/qwen3-tts
source ./env.sh
python scripts/voice_design.py --config voices/voices.json
```

Outputs:
- WAV files: `outputs/voice_design/<voice_id>.wav`
- Metadata: `outputs/voice_design/voice_design_meta.json`

### 2) Create reusable prompts

Use the voice WAVs + text to build prompt files for stable reuse:

```bash
cd ~/qwen3-tts
source ./env.sh
python scripts/create_prompts.py --config voices/voices.json
```

Outputs:
- Prompt files: `prompts/<voice_id>.pt`
- Metadata: `prompts/prompts_meta.json`

By default, `create_prompts.py` looks for reference audio at:
`outputs/voice_design/<voice_id>.wav` unless you set `ref_audio` in `voices/voices.json`.

### 3) Generate a story

**Via API (recommended):**

Stories use JSON templates (see "Story templates" below). Use the API endpoints:

```bash
# Create a story
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @stories/template.json

# Generate audio
curl -X POST http://localhost:8000/stories/template/generate

# Check job status
curl http://localhost:8000/jobs/<jobId>

# Download audio
curl http://localhost:8000/audio/stories/template/full.wav -o story.wav
```

**Via CLI:**

```bash
cd ~/qwen3-tts
source ./env.sh
python scripts/storyteller.py --story template
```

Outputs:
- Per-line WAVs in `outputs/story/<story_id>/`
- Concatenated WAV: `outputs/story/<story_id>/story_full.wav`

## Story templates (JSON only)

Stories are authored by **roles**, not voices. Voices are assigned later via casting, and
any missing casting falls back to `defaultVoiceId`. We only support English right now.

Template file: `stories/template.json` (example), schema: `docs/story-template.schema.json`.

Minimal example:

```json
{
  "schemaVersion": 1,
  "title": "Sunny Morning",
  "defaultVoiceId": "narrator_male",
  "roles": [
    { "roleId": 0, "name": "Narrator" },
    { "roleId": 1, "name": "Child" }
  ],
  "casting": {
    "0": "narrator_male",
    "1": "child"
  },
  "lines": [
    { "id": 0, "roleId": 0, "line": "It was a sunny morning in a small town." },
    { "id": 1, "roleId": 1, "line": "Can I bring my little blue bucket?", "extra": "curious, excited" }
  ]
}
```

Resolution rules:
- `voiceId = line.actorId ?? casting[roleId] ?? defaultVoiceId`
- `extra` is a performance hint and can be appended to your prompt later

Validate a template:

```bash
python scripts/validate_story.py stories/template.json
```

## API Reference

The FastAPI server provides a full REST API for story management and generation.

### Endpoints

**Health:**
- `GET /health` - Simple health check

**Voices:**
- `GET /voices` - List all available voices
- `GET /voices/{voiceId}` - Get voice details
- `GET /voices/pools` - List voice pools
- `GET /voices/pools/{poolName}` - Get voices in a pool

**Stories:**
- `GET /stories` - List all story IDs
- `POST /stories` - Create a new story template
- `GET /stories/{storyId}` - Get story template
- `PUT /stories/{storyId}` - Update story template
- `POST /stories/{storyId}/render` - Resolve roles to voices
- `POST /stories/{storyId}/generate` - Start audio generation (async job)

**Jobs:**
- `GET /jobs/{jobId}` - Get job status

**Audio:**
- `GET /audio/stories/{storyId}/full.wav` - Download concatenated audio
- `GET /audio/stories/{storyId}/files` - List per-line audio files
- `GET /audio/stories/{storyId}/files/{filename}` - Download a specific line audio file

### Interactive API docs

Visit `http://localhost:8000/docs` for interactive API documentation with request/response schemas.

### Example: Full workflow via API

```bash
# 1. Create a story
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d '{
    "schemaVersion": 1,
    "title": "My Story",
    "defaultVoiceId": "narrator_male",
    "roles": [{"roleId": 0, "name": "Narrator"}],
    "lines": [{"id": 0, "roleId": 0, "line": "Hello world"}]
  }'

# 2. Preview voice assignments
curl http://localhost:8000/stories/my_story/render

# 3. Generate audio
curl -X POST http://localhost:8000/stories/my_story/generate \
  -H "Content-Type: application/json" \
  -d '{"concat": true}'
# Note: concat defaults to true if omitted.
# Returns: {"id": "...", "status": "queued", ...}

# 4. Poll job status
curl http://localhost:8000/jobs/<jobId>
# Returns: {"id": "...", "status": "succeeded", "outputPath": "..."}

# 5. Download audio
curl http://localhost:8000/audio/stories/my_story/full.wav -o story.wav
```

## File formats

### `voices/voices.json`

This is the input for both `voice_design.py` and `create_prompts.py`. It must be a JSON array
of objects. Minimal example:

```json
[
  {
    "id": "narrator",
    "language": "English",
    "instruction": "Warm narrator, steady cadence, clear diction.",
    "sample_text": "Our story begins in a small town by the sea."
  }
]
```

Fields:
- `id` (required): filename stem for outputs (WAVs + prompts)
- `language` (optional, default `Auto`): language name passed to the model
- `instruction` (required for voice design): description for the VoiceDesign model
- `sample_text` (required for voice design): text used to synthesize the initial voice
- `ref_audio` (optional for prompt creation): custom audio path instead of `outputs/voice_design/<id>.wav`
- `ref_text` (optional for prompt creation): reference transcript for prompt extraction

Notes:
- `create_prompts.py` requires `ref_text` unless you pass `--xvec-only`.
- `ref_text` defaults to `sample_text` if not provided.

## Script reference

### `scripts/voice_design.py`

Generates one WAV per voice definition from the VoiceDesign model.

```bash
python scripts/voice_design.py \
  --config voices/voices.json \
  --out-dir outputs/voice_design \
  --model Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign \
  --device cuda:0 \
  --dtype bfloat16 \
  --attn auto \
  --max-new-tokens 4096
```

Key args:
- `--device`: `cuda:0` or `cpu`
- `--dtype`: `bf16|fp16|fp32`
- `--attn`: `auto|none|flash_attention_2`
- `--max-new-tokens`: optional cap for long generations

### `scripts/create_prompts.py`

Creates reusable `.pt` prompt files for voice cloning.

```bash
python scripts/create_prompts.py \
  --config voices/voices.json \
  --out-dir prompts \
  --model Qwen/Qwen3-TTS-12Hz-1.7B-Base \
  --device cuda:0 \
  --dtype bfloat16 \
  --attn auto
```

Extra option:
- `--xvec-only`: use x-vector only mode (skips the need for `ref_text`)

### `scripts/storyteller.py`

Generates audio from a JSON story template.

```bash
python scripts/storyteller.py \
  --story template \
  --model Qwen/Qwen3-TTS-12Hz-1.7B-Base \
  --device cuda:0 \
  --dtype bfloat16 \
  --attn auto \
  --language English \
  --no-concat  # Don't concatenate (optional)
```

Note: Story ID is the filename without `.json` extension (e.g., `stories/template.json` → `--story template`).

### `scripts/validate_story.py`

Validates a story template JSON file.

```bash
python scripts/validate_story.py stories/template.json
```

### `scripts/convert_txt.py`

Converts old `.txt` format stories to JSON template format.

The old format is `voice_id|language|text` per line (comments starting with `#` are ignored).

```bash
# Activate venv first (required)
source env.sh

# Convert a file (outputs to stories/<filename>.json)
python scripts/convert_txt.py stories/story.txt

# Specify custom output path
python scripts/convert_txt.py stories/story.txt -o stories/my_story.json

# Dry run to validate without writing
python scripts/convert_txt.py stories/story.txt --dry-run
```

The converter:
- Creates roles from unique voice IDs found in the file
- Maps each voice ID to a role via the `casting` field
- Generates a title from the filename
- Uses `narrator_male` as default voice if present, otherwise the first voice
- Validates the output against the JSON schema

## Outputs

```
outputs/
  voice_design/
    <voice_id>.wav
    voice_design_meta.json
  story/
    <story_id>/
      001_<voice_id>.wav
      002_<voice_id>.wav
      story_full.wav
prompts/
  <voice_id>.pt
  prompts_meta.json
```

## Architecture

### Library modules (`lib/`)

The codebase is organized into reusable library modules:

- **`lib/paths.py`**: Centralized path management with absolute paths
- **`lib/models.py`**: Pydantic models for API data structures
- **`lib/validation.py`**: Story template validation logic
- **`lib/resolution.py`**: Role-to-voice resolution (actorId → casting → defaultVoiceId)
- **`lib/generation.py`**: TTS generation logic with model caching support
- **`lib/storage.py`**: File-based storage utilities

### API features

- **Postgres-backed storage**: Stories, voices, pools, jobs, and metadata live in Postgres; set `DATABASE_URL` before running. Use `scripts/migrate_to_db.py` (requires `DATABASE_URL`) to import the legacy JSON/metadata into the database before starting the API. The FastAPI app and CLI scripts auto-load `.env` via `python-dotenv`, so keeping your credentials/config in the repository root is enough—no manual `source .env` steps once you run the CLI or `uvicorn api.app:app`.
- **Model caching**: TTS model loaded once and reused across generations
- **Async job system**: Non-blocking generation with status tracking
- **Validation**: Story templates validated on create/update
- **CORS enabled**: Ready for mobile web app access

The Makefile now exposes helpers for the most common database tasks:

```
make apply-migrations   # run Alembic migrations (requires .env)
make migrate-legacy    # import file-based stories/voices/metadata
make db-setup          # run migrations then import legacy data
```

Each target sources `env.sh`, so you can run them without worrying about loading `.env` separately.

### Job system

Generation runs asynchronously:
1. `POST /stories/{storyId}/generate` creates a job and returns immediately
2. Job status: `queued` → `running` → `succeeded`/`failed`
3. Poll `GET /jobs/{jobId}` for status updates
4. On success, download audio via `GET /audio/stories/{storyId}/full.wav`

Job responses include timestamps: `createdAt`, `startedAt`, and `finishedAt` (ISO 8601).

### Current async gap

The database repositories still rely on `_run_sync` wrappers that call `asyncio.run()` so the app can expose synchronous endpoints. When requests are handled inside Uvicorn/Starlette’s event loop, that shim raises “Task … got Future … attached to a different loop”, causing 500 errors on `/voices` (and any route that touches `_run_sync`). The next phase of cleanup is to convert the FastAPI routes and services to async, drop `_run_sync`, and invoke the `_async` methods directly; once that’s done the server can run without those runtime errors.

## Development tools

### Code quality

- **ruff**: Fast linter and formatter (replaces Black, isort, flake8)
- **mypy**: Static type checker
- **pytest**: Testing framework
- **pre-commit**: Git hooks for auto-formatting

### Configuration files

- `pyproject.toml`: Project metadata and tool configurations
- `.pre-commit-config.yaml`: Git hooks configuration
- `.vscode/`: VS Code settings and recommended extensions
- `Makefile`: Common development tasks

## Notes on dependencies

- CUDA toolkit 12.8 is installed at `/usr/local/cuda-12.8`.
- `env.sh` prefers CUDA 12.8 (matches torch+cu128).
- FlashAttention is installed from a prebuilt wheel that matches:
  - Linux x86_64
  - Python 3.12
  - Torch 2.8
  - CUDA 12.8

If you change Python/Torch/CUDA versions, FlashAttention may need a different wheel.

## Troubleshooting

- **Out of memory**: lower `--max-new-tokens` or switch to `--dtype fp16`.
- **No GPU**: set `--device cpu` (slow).
- **Missing SoX**: concatenation requires `sox` in PATH (we installed it in `~/.local/bin`).
- **Prompt not found**: ensure `prompts/<voice_id>.pt` exists and `voice_id` matches the story.
- **API not responding**: check that model caching loaded successfully (first request may be slow).

## Initial setup (repro steps)

1) Install UV and create venv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source ~/.local/bin/env
   uv python install 3.12
   uv venv -p 3.12 ~/qwen3-tts/.venv
   ```

2) Install qwen-tts + CUDA PyTorch:
   ```bash
   source ~/qwen3-tts/.venv/bin/activate
   uv pip install -U qwen-tts
   uv pip install --upgrade \
     torch==2.8.0+cu128 \
     torchvision==0.23.0+cu128 \
     torchaudio==2.8.0+cu128 \
     --index-url https://download.pytorch.org/whl/cu128
   ```

3) Install FlashAttention wheel:
   ```bash
   uv pip install \
     https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.7.2/flash_attn-2.8.3+cu128torch2.8-cp312-cp312-linux_x86_64.whl
   ```

4) Build SoX locally (no sudo):
   ```bash
   cd /tmp
   curl -L -o sox-14.4.2.tar.gz https://downloads.sourceforge.net/project/sox/sox/14.4.2/sox-14.4.2.tar.gz
   tar -xzf sox-14.4.2.tar.gz
   cd sox-14.4.2
   ./configure --prefix=$HOME/.local --without-alsa --without-oss --without-ladspa \
     --without-magic --without-id3tag --without-mp3 --without-flac --without-ogg \
     --without-vorbis --without-opus --without-wavpack --without-png --without-gsm
   make -j"$(nproc)"
   make install
   ```

5) Install dev tools:
   ```bash
   make dev-install
   ```

## File layout

```
qwen3-tts/
  api/
    __init__.py
    main.py              # FastAPI application
  lib/                   # Reusable library modules
    __init__.py
    paths.py
    models.py
    validation.py
    resolution.py
    generation.py
    storage.py
  scripts/
    __init__.py
    common.py
    voice_design.py
    create_prompts.py
    storyteller.py      # JSON story generation
    validate_story.py
    convert_txt.py      # Convert old .txt format to JSON
  docs/
    openapi.json
    story-template.schema.json
    web-app.md
  stories/              # JSON story templates
    template.json
  voices/
    voices.json
  prompts/              # Voice prompt files (.pt)
  outputs/
    voice_design/
    story/
  tests/                # Test files
  env.sh
  run.sh
  Makefile              # Development tasks
  pyproject.toml        # Project configuration
  requirements.txt       # Production dependencies
  .pre-commit-config.yaml
  .gitignore
```
