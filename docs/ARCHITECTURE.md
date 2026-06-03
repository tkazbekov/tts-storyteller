# TTS Storyteller API - Architecture

Multi-backend TTS system with voice-driven routing and parallel execution.

---

## System Overview

```
User Request → Voice Resolution → Backend Routing → Parallel Execution → Audio Output
```

### Key Features

- **Voice-Driven Routing:** Voices determine which backend to use
- **Parallel Execution:** Multiple backends run simultaneously
- **Backend Abstraction:** Clean interface for adding new TTS providers
- **Incremental Generation:** Only regenerate changed lines

---

## Supported Backends

| Backend | Model | Size | VRAM | Speed | Use Case |
|---------|-------|------|------|-------|----------|
| **Qwen** | Qwen3-TTS-12Hz-1.7B-Base | 3.86GB | ~4GB | Fast (~2s/line) | Narration, single-voice |
| **VibeVoice** | VibeVoice-7B (4-bit) | ~5GB | ~8GB | Slower (~5-10s/line) | Dialogue, multi-speaker |

---

## Architecture Components

### 1. Backend Abstraction (`lib/backends/`)

```python
class TTSBackend(ABC):
    @property
    def backend_name(self) -> str: ...
    
    def generate_voice_clone(self, text, language, voice_prompt): ...
    def create_voice_clone_prompt(self, ref_audio, ref_text): ...
    def save_prompt(self, prompt, path): ...
    def load_prompt(self, path): ...
```

**Implementations:**
- `QwenTTSBackend` - Wraps `qwen-tts` package
- `VibeVoiceBackend` - Skeleton (to be implemented)

### 2. Configuration (`lib/config.py`)

```python
@dataclass
class TTSConfig:
    default_backend: str = "qwen"
    device: str = "cuda:0"
    qwen_base: BackendConfig
    qwen_voice_design: BackendConfig
    vibevoice_base: BackendConfig
    vibevoice_voice_design: BackendConfig
```

**Environment Variables:**
```bash
TTS_DEFAULT_BACKEND=qwen
TTS_DEVICE=cuda:0

# Qwen
TTS_QWEN_BASE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base
TTS_QWEN_DTYPE=bfloat16
TTS_QWEN_ATTN=flash_attention_2

# VibeVoice
TTS_VIBEVOICE_BASE_MODEL=DevParker/VibeVoice7b-low-vram
TTS_VIBEVOICE_DTYPE=float16
TTS_VIBEVOICE_QUANTIZATION=4bit
```

### 3. Model Cache (`services/models.py`)

```python
def get_backend(backend_type: str, purpose: str = "base") -> TTSBackend:
    """Get cached backend instance."""
```

**Cache Structure:**
```python
{
    ("qwen", "base"): QwenTTSBackend(...),
    ("qwen", "voice_design"): QwenTTSBackend(...),
    ("vibevoice", "base"): VibeVoiceBackend(...),
}
```

### 4. Voice-Driven Routing

**Database Schema:**
```sql
CREATE TABLE voices (
    id VARCHAR(100) PRIMARY KEY,
    language VARCHAR(50),
    instruction TEXT,
    backend VARCHAR(50) DEFAULT 'qwen',  -- NEW
    ...
);
```

**Voice determines backend:**
```python
voice = await voice_repo.get("narrator")
backend = get_backend(voice.backend, "base")  # Automatic routing
```

### 5. Parallel Execution (`services/story_generation.py`)

```python
async def generate_story(story_id: str, request_params: dict) -> Path:
    # 1. Resolve voices to backends
    voice_backends = await _get_voice_backends(voice_ids)
    
    # 2. Group lines by backend
    grouped = _group_lines_by_backend(resolved_lines, voice_backends)
    
    # 3. Execute in parallel
    tasks = [
        _generate_for_backend("qwen", qwen_lines, ...),
        _generate_for_backend("vibevoice", vibe_lines, ...),
    ]
    results = await asyncio.gather(*tasks)
    
    # 4. Merge and concatenate
    return concatenated_audio_path
```

---

## File Organization

### Prompts (Backend-Specific)

```
prompts/
  qwen/
    narrator_male.pt      # PyTorch format
    old_man.pt
  vibevoice/
    child.json            # JSON format
    narrator_female.json
```

### Voice Design Outputs

```
outputs/voice_design/
  qwen/
    narrator_male.wav
  vibevoice/
    child.wav
```

### Story Outputs

```
outputs/story/
  my_story/
    001_narrator_male.wav   # Qwen
    002_child.wav           # VibeVoice
    003_old_man.wav         # Qwen
    story_full.wav          # Concatenated
```

---

## Data Flow

### Voice Creation

```
POST /voices
  ↓
VoiceConfig (includes backend)
  ↓
generate_voice_job()
  ↓
get_backend(backend, "voice_design")
  ↓
generate_voice_design() → WAV
  ↓
create_voice_clone_prompt() → Prompt
  ↓
Save to prompts/{backend}/{voice_id}.{ext}
```

### Story Generation

```
POST /stories/{id}/generate
  ↓
Resolve lines to voices
  ↓
Fetch voice.backend for each voice
  ↓
Group lines by backend
  ↓
┌─────────────┴──────────────┐
│                            │
Qwen Backend        VibeVoice Backend
(lines 0,2,4)       (lines 1,3)
  ↓                       ↓
Generate in parallel (asyncio.gather)
  ↓                       ↓
001.wav, 003.wav    002.wav, 004.wav
  └──────────┬────────────┘
             ↓
  Merge by index & concatenate
             ↓
      story_full.wav
```

---

## Performance

### RTX 3090 Memory Usage

```
Qwen Base + VoiceDesign (bfloat16):     8GB
VibeVoice (4-bit quantized):            8GB
Working memory:                         4GB
Total:                                 20GB / 24GB ✅
```

### Speed Comparison

**Sequential (single backend):**
```
20 lines × 2s = 40 seconds
```

**Parallel (mixed backends):**
```
10 Qwen lines:     10 × 2s = 20s
10 VibeVoice lines: 10 × 5s = 50s
Parallel:          max(20s, 50s) = 50s (1.25x faster)
```

**With batching:**
```
Qwen:      3 batches × 2s = 6s
VibeVoice: 2 batches × 5s = 10s
Total:     max(6s, 10s) = 10s (4x faster)
```

---

## API Usage

### Create Voice with Backend

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

### Generate Story (Automatic Routing)

```bash
curl -X POST http://localhost:8000/stories/my-story/generate
```

System automatically:
1. Resolves voices to backends
2. Groups lines by backend
3. Executes in parallel
4. Concatenates results

---

## Adding a New Backend

1. **Implement Interface:**
```python
class MyBackend(TTSBackend):
    @property
    def backend_name(self) -> str:
        return "mybackend"
    
    def generate_voice_clone(self, ...): ...
    def create_voice_clone_prompt(self, ...): ...
    def save_prompt(self, ...): ...
    def load_prompt(self, ...): ...
```

2. **Register in Factory:**
```python
# lib/backend_factory.py
TTSBackendFactory.register("mybackend", MyBackend)
```

3. **Add Configuration:**
```python
# lib/config.py
mybackend_base: BackendConfig = field(...)
```

4. **Update Environment:**
```bash
TTS_MYBACKEND_BASE_MODEL=...
TTS_MYBACKEND_DTYPE=...
```

Done! The system will automatically support the new backend.

---

## Database Schema

### Voices Table

```sql
CREATE TABLE voices (
    id VARCHAR(100) PRIMARY KEY,
    language VARCHAR(50) NOT NULL,
    instruction TEXT NOT NULL,
    sample_text TEXT,
    backend VARCHAR(50) NOT NULL DEFAULT 'qwen',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_voices_backend ON voices(backend);

ALTER TABLE voices ADD CONSTRAINT check_valid_backend 
CHECK (backend IN ('qwen', 'vibevoice'));
```

---

## Configuration Reference

### Qwen3-TTS

```bash
TTS_QWEN_BASE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base
TTS_QWEN_VOICE_DESIGN_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
TTS_QWEN_DTYPE=bfloat16
TTS_QWEN_ATTN=flash_attention_2
TTS_QWEN_MAX_NEW_TOKENS=2048
TTS_QWEN_TOP_P=0.95
TTS_QWEN_TEMPERATURE=1.0
```

**Specifications:**
- Parameters: 1.7B
- VRAM: ~4GB per model
- Speed: ~2 seconds per line
- Prompt format: PyTorch `.pt` files
- Streaming: Yes (97ms latency)

### VibeVoice

```bash
TTS_VIBEVOICE_BASE_MODEL=DevParker/VibeVoice7b-low-vram
TTS_VIBEVOICE_DTYPE=float16
TTS_VIBEVOICE_QUANTIZATION=4bit
TTS_VIBEVOICE_CFG_SCALE=3.0
TTS_VIBEVOICE_DIFFUSION_STEPS=50
```

**Specifications:**
- Parameters: ~9B total
- VRAM: ~8GB (4-bit) / ~19GB (full)
- Speed: ~5-10 seconds per line
- Prompt format: JSON files
- Streaming: No
- Multi-speaker: Up to 4 speakers

---

## Troubleshooting

### "Backend not found"
- Check `TTS_DEFAULT_BACKEND` environment variable
- Verify backend is registered in factory

### "CUDA out of memory"
- Use 4-bit quantization for VibeVoice
- Reduce batch sizes
- Check total VRAM usage

### "Prompt file not found"
- Ensure voice was created with correct backend
- Check `prompts/{backend}/{voice_id}.{ext}` exists
- Verify backend subdirectories exist
