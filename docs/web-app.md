# Qwen3-TTS Web App Plan

This app is intended for home use to manage voices, create role-based stories, and generate audio.
The backend lives in this repo; the frontend can be a separate repo.

## Goals

- Simple, local-first app for one household
- Role-first story editing with casting to voices
- One-click generation with status/progress
- Audio preview for voices and generated lines

## Backend (this repo)

### Core responsibilities

- Validate story templates against `docs/story-template.schema.json`
- Resolve role-based story templates into per-line voice assignments
- Run TTS generation as background jobs
- Serve generated audio files

### API Implementation

All endpoints are fully implemented in `api/main.py`:

- `GET /voices` - List all available voices
- `GET /voices/{voiceId}` - Get voice details
- `GET /stories` - List all story IDs
- `POST /stories` - Create story template (with validation)
- `GET /stories/{storyId}` - Get story template
- `PUT /stories/{storyId}` - Update story template (with validation)
- `POST /stories/{storyId}/render` - Resolve roles to voices
- `POST /stories/{storyId}/generate` - Start audio generation (async job). If a job is already active, returns 409; use the Jobs UI to cancel if needed.
- `GET /jobs` - List active (queued/running) jobs
- `GET /jobs/{jobId}` - Get job status
- `POST /jobs/{jobId}/cancel` - Cancel an active job (use from Jobs UI to avoid cancelling by mistake)
- `GET /audio/stories/{storyId}/full.wav` - Download concatenated audio

### Storage model

- `voices/` + `prompts/` + `outputs/` stay file-based
- `stories/` holds JSON templates (one file per story)
- Active jobs (queued/running) in-memory only; completed jobs (succeeded/failed) persisted for history

### Job runner

- Implemented as async background task processor
- Single-worker queue processes one job at a time
- Job states: `queued` → `running` → `succeeded`/`failed`
- Status reported via `/jobs/{jobId}` endpoint
- Model caching: TTS model loaded once and reused

### Features

- **Model caching**: TTS model loaded once on first use, reused for all generations
- **Async generation**: Non-blocking job system using `asyncio.to_thread()`
- **Validation**: Story templates validated on create/update
- **CORS enabled**: Ready for mobile web app access
- **File-based storage**: Simple, no database needed

## Frontend (new repo)

### Views

- Voices: list + preview + create prompt/design
- Story editor: role list + lines table + per-line notes
- Casting: map role -> voice
- Generation queue: job status + audio output

### UX notes

- Story editor should be keyboard-friendly
- Casting should highlight unassigned roles
- Use simple audio players for previews
- Poll `/jobs/{jobId}` every 1-2 seconds for status updates

## Implementation status

✅ **Completed:**
- Story template schema: `docs/story-template.schema.json`
- Story template example: `stories/template.json`
- Validator: `scripts/validate_story.py` + `lib/validation.py`
- OpenAPI spec: `docs/openapi.json`
- FastAPI implementation: `api/main.py` (fully functional)
- File-based storage for stories
- Role-to-voice resolution
- Async job system with status tracking
- Audio serving endpoint
- Model caching
- Library structure (`lib/` modules)

🚧 **Frontend (not started):**
- Story editor UI
- Casting UI
- Generation queue UI
- Audio preview components

## API Usage Example

```bash
# 1. Create a story
curl -X POST http://localhost:8000/stories \
  -H "Content-Type: application/json" \
  -d @stories/template.json

# 2. Preview voice assignments
curl http://localhost:8000/stories/template/render

# 3. Generate audio
curl -X POST http://localhost:8000/stories/template/generate \
  -H "Content-Type: application/json" \
  -d '{"concat": true}'
# Returns: {"id": "job-uuid", "status": "queued", ...}

# 4. Poll job status
curl http://localhost:8000/jobs/job-uuid
# Returns: {"id": "...", "status": "succeeded", "outputPath": "..."}

# 5. Download audio
curl http://localhost:8000/audio/stories/template/full.wav -o story.wav
```
