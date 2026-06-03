# Voice Cloning API Addition

**Date:** 2026-02-04
**Status:** ✅ Complete

---

## Problem Identified

The original API only had `POST /voices` endpoint which uses **voice design** (generating voices from text descriptions). This only works with Qwen backend, not VibeVoice.

VibeVoice requires **voice cloning** from reference audio files, not text descriptions.

---

## Solution

Added a new endpoint: `POST /voices/clone` for voice cloning from reference audio.

### New Endpoint

**POST /voices/clone**

Creates a voice by cloning from reference audio. Works with **all backends** (qwen, vibevoice).

**Request Body:** `VoiceCloneConfig`
```json
{
  "id": "voice_id",
  "language": "English",
  "instruction": "Voice description/notes",
  "ref_audio_url": "/path/to/reference.wav",
  "ref_text": "Optional transcript of reference audio",
  "backend": "vibevoice"
}
```

**Response:** Job object (202 Accepted)
```json
{
  "id": "job-uuid",
  "type": "voice_clone",
  "status": "queued",
  "voiceId": "voice_id",
  ...
}
```

---

## Backend Compatibility

| Endpoint | Qwen | VibeVoice | Method |
|----------|------|-----------|--------|
| `POST /voices` | ✅ Yes | ❌ No | Voice design from text |
| `POST /voices/clone` | ✅ Yes | ✅ Yes | Voice cloning from audio |

---

## Implementation Details

### 1. New Pydantic Model

**File:** `lib/models.py`

```python
class VoiceCloneConfig(BaseModel):
    """Voice configuration for voice cloning from reference audio."""
    id: str
    language: str
    instruction: str
    ref_audio_url: str  # Path to reference WAV file
    ref_text: str | None  # Optional transcript
    backend: str  # qwen or vibevoice
```

### 2. New API Route

**File:** `api/routes/voices.py`

- Added `POST /voices/clone` endpoint
- Validates voice doesn't already exist
- Enqueues voice cloning job
- Returns job ID for tracking

### 3. Job Processing

**File:** `services/jobs.py`

- Added `enqueue_voice_clone_job()` function
- Added `voice_clone` job type handler
- Processes `VoiceCloneConfig` from job parameters

### 4. Voice Generation Service

**File:** `services/voice_generation.py`

- Added `generate_voice_clone_job()` function
- Uses `generate_voice_prompt()` from `lib/voice_generation.py`
- Works with reference audio instead of voice design
- Saves voice metadata to repository

---

## Usage Examples

### Create Voice with Qwen (Voice Design)

```bash
curl -X POST http://localhost:8000/voices \
  -H "Content-Type: application/json" \
  -d '{
    "id": "narrator",
    "language": "English",
    "instruction": "Warm narrator voice",
    "sample_text": "Once upon a time...",
    "backend": "qwen"
  }'
```

### Clone Voice with VibeVoice (2-Step Process)

**Step 1: Upload reference audio**

```bash
curl -X POST http://localhost:8000/audio/upload \
  -F "file=@/path/to/my_voice.wav"

# Response:
# {
#   "file_path": "uploads/reference_audio/my_voice.wav",
#   "filename": "my_voice.wav",
#   "message": "File uploaded successfully..."
# }
```

**Step 2: Create voice clone**

```bash
curl -X POST http://localhost:8000/voices/clone \
  -H "Content-Type: application/json" \
  -d '{
    "id": "narrator_vibe",
    "language": "English",
    "instruction": "Warm narrator voice",
    "ref_audio_url": "uploads/reference_audio/my_voice.wav",
    "ref_text": "Once upon a time in a land far away",
    "backend": "vibevoice"
  }'
```

### Clone Voice with Qwen (Alternative)

```bash
# Step 1: Upload (same as above)
curl -X POST http://localhost:8000/audio/upload \
  -F "file=@/path/to/my_voice.wav"

# Step 2: Clone with Qwen backend
curl -X POST http://localhost:8000/voices/clone \
  -H "Content-Type: application/json" \
  -d '{
    "id": "custom_voice",
    "language": "English",
    "instruction": "Custom voice from audio",
    "ref_audio_url": "uploads/reference_audio/my_voice.wav",
    "ref_text": "Hello, this is my voice",
    "backend": "qwen"
  }'
```

---

## Workflow Comparison

### Voice Design (POST /voices)

```
1. User provides text description
2. Qwen VoiceDesign model generates WAV
3. Qwen Base model creates prompt from WAV
4. Voice ready to use
```

**Limitations:** Qwen only

### Voice Cloning (POST /voices/clone)

```
1. User provides reference WAV file
2. Backend creates prompt directly from WAV
3. Voice ready to use
```

**Benefits:** Works with all backends

---

## Error Handling

### Using Voice Design with VibeVoice

```bash
POST /voices with backend: "vibevoice"
```

**Response:** 400 Bad Request
```json
{
  "detail": "Voice design is only supported for 'qwen' backend. For 'vibevoice' backend, use POST /voices/clone with reference audio."
}
```

### Missing Reference Audio

```bash
POST /voices/clone with non-existent ref_audio_url
```

**Response:** Job fails with error message:
```json
{
  "status": "failed",
  "message": "Reference audio not found: /path/to/missing.wav"
}
```

---

## OpenAPI Schema Updates

### VoiceCloneConfig Schema

```json
{
  "VoiceCloneConfig": {
    "type": "object",
    "required": ["id", "language", "instruction", "ref_audio_url"],
    "properties": {
      "id": {
        "type": "string",
        "minLength": 1,
        "description": "Voice identifier"
      },
      "language": {
        "type": "string",
        "minLength": 1,
        "description": "Language for this voice"
      },
      "instruction": {
        "type": "string",
        "minLength": 1,
        "description": "Voice description/notes"
      },
      "ref_audio_url": {
        "type": "string",
        "minLength": 1,
        "description": "URL or path to reference audio file (WAV format)"
      },
      "ref_text": {
        "type": "string",
        "nullable": true,
        "description": "Optional transcript of reference audio"
      },
      "backend": {
        "type": "string",
        "default": "qwen",
        "description": "TTS backend to use (qwen, vibevoice)"
      }
    }
  }
}
```

---

## Files Modified

1. **lib/models.py** - Added `VoiceCloneConfig` model with workflow documentation
2. **api/routes/voices.py** - Added `POST /voices/clone` endpoint
3. **api/routes/audio.py** - Added `POST /audio/upload` endpoint for file uploads
4. **services/jobs.py** - Added `enqueue_voice_clone_job()` and handler
5. **services/voice_generation.py** - Added `generate_voice_clone_job()`
6. **.gitignore** - Added `uploads/` directory
7. **docs/openapi.json** - Regenerated with new endpoints
8. **docs/SWAGGER.md** - Updated documentation with upload workflow

---

## Testing

### Type Checking
```bash
mypy api/routes/voices.py services/jobs.py services/voice_generation.py lib/models.py
# ✅ Success: no issues found in 4 source files
```

### Linting
```bash
ruff check api/routes/voices.py services/jobs.py services/voice_generation.py lib/models.py
# ✅ All checks passed!
```

### OpenAPI Validation
```bash
# Endpoint present in spec
curl http://localhost:8000/openapi.json | jq '.paths["/voices/clone"]'
# ✅ Returns endpoint definition
```

---

## Swagger UI

The new endpoint is available in Swagger UI at:

**http://localhost:8000/docs**

Navigate to:
- **POST /voices** - Voice design (Qwen only)
- **POST /voices/clone** - Voice cloning (all backends) ⭐ NEW

---

## Benefits

1. ✅ **VibeVoice Support** - Can now create VibeVoice voices
2. ✅ **Flexibility** - Users can choose voice design OR voice cloning
3. ✅ **Reusability** - Can clone voices from existing audio files
4. ✅ **Backend Agnostic** - Clone endpoint works with all backends
5. ✅ **Clear API** - Separate endpoints for different creation methods

---

**Implementation Complete!** 🎉
