# TTS Storyteller API - Documentation

Multi-backend text-to-speech system with voice-driven routing and parallel execution.

---

## Quick Start

```bash
# Setup
cd ~/qwen3-tts
source env.sh
make install
pip install -r requirements-qwen.txt

# Configure
cp .env.example .env
# Edit .env with your settings

# Run migrations
alembic upgrade head

# Start API
make run-api
```

---

## Documentation

### Core Documentation

**[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design
- Backend abstraction layer
- Voice-driven routing
- Parallel execution model
- File organization
- Performance characteristics

**[BACKENDS.md](BACKENDS.md)** - Backend specifications
- Qwen3-TTS specifications
- VibeVoice specifications
- Configuration reference
- Performance comparison

**[SWAGGER.md](SWAGGER.md)** - Interactive API documentation
- Swagger UI usage
- API endpoints reference
- Request/response examples
- Backend field usage

**[web-app.md](web-app.md)** - Web application documentation

---

## Key Concepts

### Voice-Driven Routing

Voices determine which backend to use:

```python
# Create voice with specific backend
{
  "id": "narrator",
  "backend": "qwen",      # Fast, streaming
  "language": "English",
  "instruction": "Warm narrator voice"
}

{
  "id": "child",
  "backend": "vibevoice",  # Natural dialogue
  "language": "English",
  "instruction": "Energetic child voice"
}
```

System automatically routes generation to the correct backend.

### Parallel Execution

Multiple backends run simultaneously:

```
Story with mixed voices:
  Line 0: narrator (qwen)      ─┐
  Line 1: child (vibevoice)     ├─ Execute in parallel
  Line 2: narrator (qwen)      ─┘
  
Result: 2-6x faster generation
```

---

## Configuration

### Environment Variables

```bash
# Default backend
TTS_DEFAULT_BACKEND=qwen
TTS_DEVICE=cuda:0

# Qwen (fast, streaming)
TTS_QWEN_BASE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base
TTS_QWEN_DTYPE=bfloat16
TTS_QWEN_ATTN=flash_attention_2

# VibeVoice (dialogue, multi-speaker)
TTS_VIBEVOICE_BASE_MODEL=DevParker/VibeVoice7b-low-vram
TTS_VIBEVOICE_DTYPE=float16
TTS_VIBEVOICE_QUANTIZATION=4bit
```

See `.env.example` for complete configuration.

---

## API Usage

### Create Voice

```bash
curl -X POST http://localhost:8000/voices \
  -H "Content-Type: application/json" \
  -d '{
    "id": "narrator",
    "language": "English",
    "instruction": "Warm, authoritative narrator",
    "sample_text": "Once upon a time...",
    "backend": "qwen"
  }'
```

### Generate Story

```bash
curl -X POST http://localhost:8000/stories/my-story/generate
```

System automatically:
1. Resolves voices to backends
2. Groups lines by backend
3. Executes in parallel
4. Concatenates results

---

## Development

### Commands

```bash
# Install dependencies
make install          # Production dependencies
make dev-install      # Development tools

# Code quality
make format           # Format code
make lint             # Check code style
make type-check       # Type checking
make test             # Run tests
make check            # All checks

# Run
make run-api          # Start API server
```

### Project Structure

```
api/                  # FastAPI application
  routes/             # API endpoints
lib/                  # Core library
  backends/           # Backend implementations
  repositories/       # Data access
services/             # Business logic
scripts/              # CLI tools
tests/                # Test suite
```

---

## Backend Comparison

| | Qwen | VibeVoice |
|---|---|---|
| **Speed** | Fast (~2s/line) | Slower (~5-10s/line) |
| **VRAM** | 4GB | 8GB (4-bit) |
| **Streaming** | ✅ Yes | ❌ No |
| **Multi-speaker** | ❌ No | ✅ Yes |
| **Voice Design** | ✅ Yes | ❌ No |
| **Languages** | 10 | English, Chinese |

---

## Troubleshooting

### CUDA out of memory
- Use 4-bit quantization for VibeVoice
- Check total VRAM usage: `nvidia-smi`

### Prompt file not found
- Ensure voice created with correct backend
- Check `prompts/{backend}/{voice_id}.{ext}` exists

### Backend not found
- Verify `TTS_DEFAULT_BACKEND` environment variable
- Check backend registered in factory

---

## Resources

- **API Docs:** http://localhost:8000/docs (when running)
- **OpenAPI Spec:** [openapi.json](openapi.json)
- **Story Schema:** [story-template.schema.json](story-template.schema.json)

---

**Version:** 1.0  
**Last Updated:** 2026-02-04
