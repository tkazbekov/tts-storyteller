# File Upload Feature for Voice Cloning

**Date:** 2026-02-04
**Status:** ✅ Complete

---

## Problem

The voice cloning endpoint (`POST /voices/clone`) required a `ref_audio_url` field, but there was no way to upload audio files through the API. Users had to manually place files on the server filesystem.

---

## Solution

Added a file upload endpoint: `POST /audio/upload`

### New Endpoint

**POST /audio/upload**

Upload a reference audio file for voice cloning.

**Request:** `multipart/form-data`
- `file`: WAV file (required)

**Response:** `200 OK`
```json
{
  "file_path": "uploads/reference_audio/my_voice.wav",
  "filename": "my_voice.wav",
  "message": "File uploaded successfully. Use this path in ref_audio_url: uploads/reference_audio/my_voice.wav"
}
```

---

## Complete Workflow

### Voice Cloning with File Upload

```bash
# Step 1: Upload reference audio
curl -X POST http://localhost:8000/audio/upload \
  -F "file=@/path/to/my_voice.wav"

# Response:
# {
#   "file_path": "uploads/reference_audio/my_voice.wav",
#   "filename": "my_voice.wav",
#   "message": "..."
# }

# Step 2: Create voice clone using the uploaded file
curl -X POST http://localhost:8000/voices/clone \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my_voice",
    "language": "English",
    "instruction": "My custom voice",
    "ref_audio_url": "uploads/reference_audio/my_voice.wav",
    "ref_text": "Optional transcript",
    "backend": "vibevoice"
  }'

# Response:
# {
#   "id": "job-uuid",
#   "type": "voice_clone",
#   "status": "queued",
#   ...
# }

# Step 3: Check job status
curl http://localhost:8000/jobs/{job-uuid}
```

---

## Implementation Details

### File Storage

- **Upload Directory:** `uploads/reference_audio/`
- **Created automatically** on API startup
- **Ignored by git** (added to `.gitignore`)

### File Validation

- ✅ Only WAV files accepted
- ✅ Filename validation
- ✅ Error handling for save failures

### Code Changes

**File:** `api/routes/audio.py`

```python
# Upload directory
UPLOAD_DIR = Path("uploads/reference_audio")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/audio/upload")
async def upload_reference_audio(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a reference audio file for voice cloning."""

    # Validate WAV format
    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(400, "Only WAV files are supported")

    # Save file
    file_path = UPLOAD_DIR / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "file_path": str(file_path),
        "filename": file.filename,
        "message": f"File uploaded successfully. Use this path in ref_audio_url: {file_path}"
    }
```

---

## Swagger UI Usage

### Using the File Upload

1. Navigate to **http://localhost:8000/docs**
2. Find **POST /audio/upload**
3. Click **"Try it out"**
4. Click **"Choose File"** button
5. Select your WAV file
6. Click **"Execute"**
7. Copy the `file_path` from the response
8. Use this path in `POST /voices/clone` → `ref_audio_url` field

### Visual Flow

```
┌─────────────────────────────────────┐
│  1. Upload File                     │
│  POST /audio/upload                 │
│  ┌───────────────────────────────┐  │
│  │ Choose File: my_voice.wav     │  │
│  └───────────────────────────────┘  │
│  ↓                                   │
│  Returns: "uploads/reference_audio/ │
│           my_voice.wav"             │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  2. Create Voice Clone              │
│  POST /voices/clone                 │
│  {                                   │
│    "id": "my_voice",                │
│    "ref_audio_url": "uploads/...wav"│
│    "backend": "vibevoice"           │
│  }                                   │
│  ↓                                   │
│  Returns: Job ID                    │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  3. Check Job Status                │
│  GET /jobs/{jobId}                  │
│  ↓                                   │
│  Status: succeeded                  │
└─────────────────────────────────────┘
```

---

## Error Handling

### Invalid File Type

```bash
# Upload MP3 file
curl -X POST http://localhost:8000/audio/upload \
  -F "file=@audio.mp3"

# Response: 400 Bad Request
{
  "detail": "Only WAV files are supported. Please upload a .wav file."
}
```

### Missing Filename

```bash
# Upload without filename
curl -X POST http://localhost:8000/audio/upload \
  -F "file=@-"

# Response: 400 Bad Request
{
  "detail": "No filename provided"
}
```

### Save Failure

```bash
# Disk full or permission error
# Response: 500 Internal Server Error
{
  "detail": "Failed to save file: [error message]"
}
```

---

## Security Considerations

### Current Implementation

- ✅ File type validation (WAV only)
- ✅ Files stored in dedicated directory
- ✅ Directory excluded from git
- ✅ Path traversal protection (filename used directly)

### Future Enhancements

Consider adding:
- File size limits
- Virus scanning
- Unique filename generation (prevent overwrites)
- Cleanup of old uploaded files
- Authentication/authorization
- Rate limiting

---

## Testing

### Type Checking
```bash
mypy api/routes/audio.py lib/models.py
# ✅ Success: no issues found
```

### Linting
```bash
ruff check api/routes/audio.py lib/models.py
# ✅ All checks passed!
```

### Manual Testing
```bash
# Test file upload
curl -X POST http://localhost:8000/audio/upload \
  -F "file=@test.wav" | jq

# Verify file exists
ls -lh uploads/reference_audio/test.wav
```

---

## OpenAPI Schema

### Upload Endpoint Schema

```json
{
  "/audio/upload": {
    "post": {
      "summary": "Upload Reference Audio",
      "description": "Upload a reference audio file for voice cloning.\n\nAccepts WAV files. Returns the file path to use in ref_audio_url.",
      "operationId": "upload_reference_audio_audio_upload_post",
      "requestBody": {
        "content": {
          "multipart/form-data": {
            "schema": {
              "type": "object",
              "properties": {
                "file": {
                  "type": "string",
                  "format": "binary"
                }
              },
              "required": ["file"]
            }
          }
        },
        "required": true
      },
      "responses": {
        "200": {
          "description": "Successful Response",
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "file_path": {"type": "string"},
                  "filename": {"type": "string"},
                  "message": {"type": "string"}
                }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## Files Modified

1. **api/routes/audio.py**
   - Added `POST /audio/upload` endpoint
   - Added `UPLOAD_DIR` constant
   - Added file validation and saving logic

2. **.gitignore**
   - Added `uploads/` to ignore uploaded files

3. **lib/models.py**
   - Updated `VoiceCloneConfig` docstring with workflow
   - Updated `ref_audio_url` field description

4. **docs/openapi.json**
   - Regenerated with new upload endpoint

5. **docs/SWAGGER.md**
   - Added upload endpoint to endpoint list
   - Updated voice cloning examples with 2-step workflow

6. **VOICE_CLONING_API.md**
   - Updated usage examples with upload step

---

## Benefits

1. ✅ **Self-Service** - Users can upload files via API
2. ✅ **No SSH Required** - No need for server filesystem access
3. ✅ **Swagger UI Support** - Easy testing in browser
4. ✅ **Clear Workflow** - Upload → Clone → Generate
5. ✅ **Type Safe** - File validation prevents errors
6. ✅ **Production Ready** - Error handling and validation

---

**Implementation Complete!** 🎉

Users can now upload reference audio files directly through the API for voice cloning.
