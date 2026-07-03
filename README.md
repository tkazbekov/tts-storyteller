# TTS Storyteller

Local multi-backend text-to-speech tools for generating multi-voice stories.

TTS Storyteller is an independent API/CLI wrapper around third-party TTS models. It is not an official Qwen or VibeVoice project. The app currently supports:

- Qwen3-TTS for fast story narration, text-described voice design, and voice-clone prompts.
- VibeVoice for experimental reference-audio voice cloning and long-form dialogue.
- FastAPI endpoints for voices, stories, jobs, and audio downloads/uploads.
- CLI scripts for prompt creation, story validation, and generation.

Status: usable local project, still early. Qwen is the main tested path. VibeVoice support is implemented but should be treated as experimental until you run an end-to-end generation on your GPU.

## Quick start

One command from a fresh clone:

```bash
./scripts/start.sh
```

That script creates `.venv`, installs dependencies, creates `.env` if missing, starts Postgres with Docker Compose when Docker is available, runs migrations, pre-downloads the configured Hugging Face models, and starts the API.

Then open:

```text
http://localhost:8000/docs
```

If you only want Qwen or VibeVoice dependencies/models:

```bash
./scripts/start.sh --backend qwen
./scripts/start.sh --backend vibevoice
./scripts/start.sh --backend all
```

Skip the heavy model download when you only want the API shell:

```bash
./scripts/start.sh --skip-model-download
```

## Manual setup

Requirements:

- Linux
- Python 3.12
- CUDA-capable GPU recommended
- `uv` (installed automatically by `scripts/start.sh` if missing)
- Docker Compose for local Postgres, or your own `DATABASE_URL`

Dependencies are declared in `pyproject.toml` and pinned in the committed
`uv.lock`. `uv sync` installs the exact locked set for the chosen extras and
removes anything else, so pick one install target rather than stacking them:

```bash
git clone <your-repo-url> tts-storyteller
cd tts-storyteller
cp .env.example .env
make install-qwen       # base + Qwen backend (or: install, install-vibevoice, install-all)
source env.sh
make db-up
make db-setup
make download-models BACKEND=qwen
make run-api
```

## Configuration

Most settings live in `.env`:

```bash
TTS_DEFAULT_BACKEND=qwen
TTS_DEVICE=cuda:0
DATABASE_URL=postgresql+asyncpg://tts_storyteller:dev_password@localhost:5432/tts_storyteller

TTS_QWEN_BASE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base
TTS_QWEN_VOICE_DESIGN_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
TTS_QWEN_DTYPE=bfloat16
TTS_QWEN_ATTN=flash_attention_2

TTS_VIBEVOICE_BASE_MODEL=DevParker/VibeVoice7b-low-vram
TTS_VIBEVOICE_DTYPE=float16
TTS_VIBEVOICE_QUANTIZATION=4bit
```

See `.env.example` for the full list.

## Backends

| Backend | Best for | Voice design | Voice cloning | Notes |
|---|---|---:|---:|---|
| Qwen3-TTS | Fast single-voice narration and reusable prompts | yes | yes | Main path. Uses `.pt` prompt files. |
| VibeVoice | Natural dialogue and long-form audio | no | yes | Experimental in this repo. Requires reference WAV files. |

Model weights are downloaded by Hugging Face tooling into your normal HF cache, not committed into this repository.

## Repository layout

```text
api/                  FastAPI app and routes
lib/                  Core models, storage, backends, config, generation helpers
services/             Async job orchestration and API service layer
scripts/              Setup, model download, and generation CLIs
stories/              Example story templates
voices/               Example voice and pool definitions
prompts/              Small reusable prompt examples and generated prompt placeholders
outputs/              Runtime audio output placeholders only
docs/                 Architecture, backend, API, and feature notes
tests/                Unit tests
```

Generated data is intentionally ignored:

- `.venv/`
- `.env`
- `uploads/`
- generated WAVs under `outputs/`
- caches such as `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`

## API workflow

Start the API:

```bash
make run-api
```

Create a story:

```bash
curl -X POST http://localhost:8000/stories   -H "Content-Type: application/json"   -d @stories/template.json
```

Generate audio:

```bash
curl -X POST http://localhost:8000/stories/template/generate   -H "Content-Type: application/json"   -d '{"concat": true}'
```

Poll the returned job:

```bash
curl http://localhost:8000/jobs/<jobId>
```

Download the final WAV:

```bash
curl http://localhost:8000/audio/stories/template/full.wav -o story.wav
```

Upload reference audio for voice cloning:

```bash
curl -X POST http://localhost:8000/audio/upload   -F "file=@reference.wav"
```

Create a cloned voice from the returned `file_path`:

```bash
curl -X POST http://localhost:8000/voices/clone   -H "Content-Type: application/json"   -d '{
    "id": "my_voice",
    "backend": "qwen",
    "language": "English",
    "instruction": "Reference speaker",
    "ref_audio_url": "uploads/reference_audio/<uploaded-file>.wav",
    "ref_text": "Transcript of the reference clip"
  }'
```

## CLI workflow

Validate a story:

```bash
python scripts/validate_story.py stories/template.json
```

Design Qwen voices from `voices/voices.json`:

```bash
python scripts/voice_design.py --config voices/voices.json
```

Create reusable Qwen prompts:

```bash
python scripts/create_prompts.py --config voices/voices.json
```

Generate a story from the CLI:

```bash
python scripts/storyteller.py --story template
```

Download configured models without starting the API:

```bash
python scripts/download_models.py --backend qwen
python scripts/download_models.py --backend all
```

## Development

```bash
make help
make format
make lint
make type-check
make test
make check
```

Before publishing or pushing a release branch, run:

```bash
make check
git diff --check
```

Then review tracked files for local paths, LAN hostnames/IPs, and secret values before pushing.

## Documentation

- `docs/ARCHITECTURE.md` - system design and data flow
- `docs/BACKENDS.md` - backend details and model tradeoffs
- `docs/SWAGGER.md` - API examples and Swagger usage
- `docs/features/` - implementation notes for upload, cloning, and VibeVoice work
- `docs/openapi.json` - OpenAPI export
- `docs/story-template.schema.json` - story template JSON schema

## License

This repository is MIT licensed. See `LICENSE`.

Third-party model weights and packages are governed by their own licenses and terms. Check the relevant Qwen3-TTS and VibeVoice model/package pages before redistributing models or generated assets.
