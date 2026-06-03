# Swagger UI Documentation

The TTS Storyteller API includes interactive Swagger UI documentation for easy API exploration and testing.

---

## Accessing Swagger UI

### When API is Running

Start the API server:

```bash
cd tts-storyteller
source env.sh
make run-api
```

Then open your browser to:

**http://localhost:8000/docs**

---

## Features

### Interactive API Documentation

- **Explore all endpoints** - Browse all available API routes
- **View request/response schemas** - See exact data structures
- **Try it out** - Execute API calls directly from the browser
- **View examples** - See sample requests and responses

### Key Endpoints

#### Voices

- `GET /voices` - List all voices (with optional pool filter)
- `GET /voices/{voiceId}` - Get voice details
- `POST /voices` - Create new voice using voice design (Qwen only, returns job ID)
- `POST /voices/clone` - Create new voice using voice cloning (all backends, returns job ID)
- `PUT /voices/{voiceId}` - Update voice configuration
- `DELETE /voices/{voiceId}` - Delete voice

#### Audio

- `POST /audio/upload` - Upload reference audio file for voice cloning ⭐ NEW
- `GET /audio/voices/{voiceId}.wav` - Download voice reference audio
- `GET /audio/stories/{storyId}/full.wav` - Download concatenated story audio
- `GET /audio/stories/{storyId}/files` - List story audio files
- `GET /audio/stories/{storyId}/files/{filename}` - Download specific story audio file

#### Stories

- `GET /stories` - List all stories
- `GET /stories/{storyId}` - Get story details
- `POST /stories` - Create story from template
- `PUT /stories/{storyId}` - Update story template
- `POST /stories/{storyId}/generate` - Generate audio (returns job ID)
- `DELETE /stories/{storyId}` - Delete story

#### Jobs

- `GET /jobs` - List all jobs (with status filter)
- `GET /jobs/{jobId}` - Get job status and progress

#### Pools

- `GET /pools` - List all voice pools
- `POST /pools` - Create voice pool
- `PUT /pools/{poolName}` - Update pool voices
- `DELETE /pools/{poolName}` - Delete pool

#### Audio

- `GET /audio/story/{storyId}` - Download story audio
- `GET /audio/story/{storyId}/{lineIndex}` - Download line audio
- `GET /audio/voice/{voiceId}` - Download voice reference audio

---

## Using the Backend Field

### Creating a Voice with Specific Backend

**Qwen (default):**
```json
{
  "id": "narrator_qwen",
  "language": "English",
  "instruction": "Warm, authoritative narrator",
  "sample_text": "Once upon a time...",
  "backend": "qwen"
}
```

**VibeVoice:**
```json
{
  "id": "narrator_vibe",
  "language": "English",
  "instruction": "Warm, authoritative narrator",
  "sample_text": "Once upon a time...",
  "backend": "vibevoice"
}
```

### Voice Schema

The `Voice` object includes:

```json
{
  "id": "string",
  "language": "string",
  "instruction": "string",
  "sample_text": "string | null",
  "backend": "string (default: qwen)",
  "promptPath": "string | null",
  "refAudioPath": "string | null"
}
```

### VoiceConfig Schema

When creating/updating voices:

```json
{
  "id": "string (required)",
  "language": "string (required)",
  "instruction": "string (required)",
  "sample_text": "string (required)",
  "backend": "string (default: qwen)"
}
```

---

## Example Workflows

### 1. Create Voice with Qwen (Voice Design)

```bash
# Using Swagger UI:
1. Navigate to POST /voices
2. Click "Try it out"
3. Enter request body:
{
  "id": "narrator",
  "language": "English",
  "instruction": "Professional narrator voice",
  "sample_text": "Welcome to the story",
  "backend": "qwen"
}
4. Click "Execute"
5. Note the job ID in response
6. Check job status at GET /jobs/{jobId}
```

### 2. Clone Voice with VibeVoice (Voice Cloning)

```bash
# Note: Requires VibeVoice dependencies installed
# pip install -r requirements-vibevoice.txt

# Step 1: Upload reference audio
1. Navigate to POST /audio/upload
2. Click "Try it out"
3. Click "Choose File" and select your WAV file
4. Click "Execute"
5. Copy the "file_path" from the response (e.g., "uploads/reference_audio/my_voice.wav")

# Step 2: Create voice clone
1. Navigate to POST /voices/clone
2. Click "Try it out"
3. Enter request body (use the file_path from Step 1):
{
  "id": "dialogue_voice",
  "language": "English",
  "instruction": "Natural conversational voice",
  "ref_audio_url": "uploads/reference_audio/my_voice.wav",
  "ref_text": "This is the reference audio transcript",
  "backend": "vibevoice"
}
4. Click "Execute"
5. Monitor job progress at GET /jobs/{jobId}
```

### 3. Clone Voice with Qwen (Alternative)

```bash
# You can also use voice cloning with Qwen backend

# Step 1: Upload reference audio (same as above)
1. Navigate to POST /audio/upload
2. Upload your WAV file
3. Copy the file_path from response

# Step 2: Create voice clone with Qwen
1. Navigate to POST /voices/clone
2. Use request body with "backend": "qwen"
{
  "id": "custom_voice",
  "language": "English",
  "instruction": "Custom voice from audio",
  "ref_audio_url": "uploads/reference_audio/my_voice.wav",
  "ref_text": "Hello, this is my voice",
  "backend": "qwen"
}
3. This creates a voice from reference audio instead of text description
```

### 4. Generate Story with Mixed Backends

```bash
# Story lines will automatically route to correct backend
# based on voice assignments

1. Create story template with mixed voices:
{
  "defaultVoiceId": "narrator",  # Qwen backend
  "language": "English",
  "casting": {
    "character1": "dialogue_voice"  # VibeVoice backend
  },
  "lines": [
    {"text": "Once upon a time...", "roleId": "narrator"},
    {"text": "Hello!", "roleId": "character1"},
    {"text": "And so it began.", "roleId": "narrator"}
  ]
}

2. POST to /stories to create
3. POST to /stories/{storyId}/generate
4. System automatically:
   - Groups lines by backend
   - Executes in parallel
   - Concatenates results
```

---

## Alternative: ReDoc

For a different documentation style, visit:

**http://localhost:8000/redoc**

ReDoc provides a cleaner, more readable format but without interactive testing.

---

## OpenAPI Specification

The raw OpenAPI 3.1.0 specification is available at:

- **File:** `docs/openapi.json`
- **Endpoint:** http://localhost:8000/openapi.json

You can import this into tools like:
- Postman
- Insomnia
- Swagger Editor
- API clients

---

## Tips

### Authentication

Currently no authentication is required. For production use, consider adding:
- API keys
- JWT tokens
- OAuth2

### CORS

CORS is configured via environment variable:

```bash
TTS_CORS_ORIGINS=http://localhost:3000,https://myapp.com
# or
TTS_CORS_ORIGINS=*  # Allow all (development only)
```

### Rate Limiting

Consider adding rate limiting for production:
- Per-IP limits
- Per-endpoint limits
- Job queue limits

---

## Troubleshooting

### "Backend not found" errors

Make sure the backend is properly configured:
- Qwen: Always available (default)
- VibeVoice: Requires `pip install -r requirements-vibevoice.txt`

### Job stays in "queued" state

Check:
- Worker is running (started automatically with API)
- No errors in console logs
- Required model files are accessible

### 422 Validation Error

Check request body matches schema exactly:
- All required fields present
- Correct data types
- Valid enum values (e.g., backend must be "qwen" or "vibevoice")
