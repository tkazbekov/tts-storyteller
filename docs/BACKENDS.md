# TTS Backend Specifications

Technical specifications for supported TTS backends.

---

## Qwen3-TTS-12Hz-1.7B

### Model Information

- **Model ID:** `Qwen/Qwen3-TTS-12Hz-1.7B-Base`
- **Parameters:** 1.7 billion
- **Size:** 3.86 GB
- **License:** Apache 2.0
- **Package:** `qwen-tts>=0.0.5`

### Variants

```
Qwen3-TTS-12Hz-1.7B-Base          # Voice cloning
Qwen3-TTS-12Hz-1.7B-VoiceDesign   # Voice design from descriptions
Qwen3-TTS-12Hz-1.7B-CustomVoice   # 9 pre-made voices
Qwen3-TTS-12Hz-0.6B-Base          # Smaller variant
```

### Performance

- **VRAM:** ~4 GB (bfloat16)
- **Speed:** ~2 seconds per line
- **Latency:** 97ms first token (streaming)
- **Max Length:** Unlimited (streaming)
- **Sample Rate:** 24 kHz

### Features

- ✅ Streaming generation
- ✅ Voice cloning (3-second reference)
- ✅ Voice design from text descriptions
- ✅ 10 languages
- ✅ FlashAttention 2 support
- ❌ Multi-speaker (single voice per generation)

### Configuration

```bash
TTS_QWEN_BASE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base
TTS_QWEN_VOICE_DESIGN_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
TTS_QWEN_DTYPE=bfloat16
TTS_QWEN_ATTN=flash_attention_2
TTS_QWEN_MAX_NEW_TOKENS=2048
TTS_QWEN_TOP_P=0.95
TTS_QWEN_TEMPERATURE=1.0
```

### Prompt Format

**File:** `.pt` (PyTorch serialized)

```python
{
    "items": [
        {
            "ref_code": [[...], [...], ...],      # Acoustic codes
            "ref_spk_embedding": [...],           # Speaker embedding
            "x_vector_only_mode": False,
            "icl_mode": True,
            "ref_text": "Reference transcript",
        }
    ]
}
```

**Size:** ~100KB - 2MB per voice

### API Usage

```python
from qwen_tts import Qwen3TTSModel

model = Qwen3TTSModel.from_pretrained(
    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device_map="cuda:0",
    dtype=torch.bfloat16,
    attn_implementation="flash_attention_2",
)

# Voice cloning
wavs, sr = model.generate_voice_clone(
    text="Hello world",
    language="English",
    ref_audio="reference.wav",
    ref_text="Reference transcript",
)

# Create reusable prompt
prompt = model.create_voice_clone_prompt(
    ref_audio="reference.wav",
    ref_text="Reference transcript",
)
```

### Languages

Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian

### Best For

- Fast generation
- Streaming output
- Single-voice narration
- Voice design from descriptions
- Multi-language content

---

## VibeVoice-7B

### Model Information

- **Model ID:** `vibevoice/VibeVoice-7B`
- **Parameters:** ~9B total (7B LLM + 2B tokenizers/diffusion)
- **Size:** 18.7 GB (full) / ~5 GB (4-bit)
- **License:** MIT
- **Package:** Custom implementation (official code temporarily unavailable)

### Architecture

- **Base LLM:** Qwen2.5-1.5B
- **Acoustic Tokenizer:** σ-VAE (~340M params)
- **Semantic Tokenizer:** ASR encoder (~340M params)
- **Diffusion Head:** DDPM (~600M params)
- **Frame Rate:** 7.5 Hz
- **Context Length:** Up to 32,768 tokens

### Performance

- **VRAM:** ~19 GB (full) / ~8 GB (4-bit) / ~12 GB (8-bit)
- **Speed:** ~5-10 seconds per line (diffusion overhead)
- **Max Length:** 90 minutes
- **Max Speakers:** 4 simultaneous
- **Sample Rate:** 24 kHz

### Features

- ✅ Multi-speaker (up to 4)
- ✅ Long-form generation (90 minutes)
- ✅ Voice cloning
- ❌ Streaming
- ❌ Voice design from text
- ❌ FlashAttention

### Configuration

```bash
# Recommended: 4-bit quantized
TTS_VIBEVOICE_BASE_MODEL=DevParker/VibeVoice7b-low-vram
TTS_VIBEVOICE_DTYPE=float16
TTS_VIBEVOICE_QUANTIZATION=4bit
TTS_VIBEVOICE_CFG_SCALE=3.0
TTS_VIBEVOICE_DIFFUSION_STEPS=50

# Full precision (requires 19GB VRAM)
# TTS_VIBEVOICE_BASE_MODEL=vibevoice/VibeVoice-7B
# TTS_VIBEVOICE_QUANTIZATION=none
```

### Prompt Format

**File:** `.json` (JSON)

```json
{
  "backend": "vibevoice",
  "voice_id": "narrator_female",
  "speaker_profile": {
    "ref_audio_path": "outputs/voice_design/vibevoice/narrator_female.wav",
    "description": "Female narrator, warm and engaging",
    "language": "English",
    "acoustic_features": {
      "embedding": [...],
      "semantic_codes": [...]
    }
  }
}
```

**Size:** ~50KB - 500KB per voice

### API Usage

**Note:** Implementation pending. Expected API:

```python
# Expected usage (to be implemented)
from vibevoice import VibeVoiceModel

model = VibeVoiceModel.from_pretrained(
    "vibevoice/VibeVoice-7B",
    device_map="cuda:0",
    torch_dtype=torch.float16,
    load_in_4bit=True,
)

# Multi-speaker generation
audio, sr = model.generate(
    script=[
        {"speaker": "Speaker1", "text": "Hello!"},
        {"speaker": "Speaker2", "text": "Hi there!"},
    ],
    speaker_profiles={...}
)
```

### Languages

English (native), Chinese (native)

**Note:** Other languages experimental/unsupported

### Best For

- Multi-speaker dialogue
- Long-form content (podcasts, audiobooks)
- Natural conversation
- English/Chinese content

---

## Comparison

| Feature | Qwen3-TTS | VibeVoice |
|---------|-----------|-----------|
| **Speed** | ⚡ Fast (~2s/line) | 🐢 Slower (~5-10s/line) |
| **VRAM** | 💚 Low (4GB) | 🟡 Medium (8GB 4-bit) |
| **Streaming** | ✅ Yes | ❌ No |
| **Multi-speaker** | ❌ No | ✅ Yes (4 speakers) |
| **Voice Design** | ✅ Yes | ❌ No |
| **Languages** | 10 languages | English, Chinese |
| **Prompt Format** | `.pt` (PyTorch) | `.json` (JSON) |
| **Max Length** | Unlimited | 90 minutes |

---

## RTX 3090 Configuration

### Recommended Setup (Both Backends)

```bash
TTS_DEVICE=cuda:0

# Qwen: Full precision (fast, high quality)
TTS_QWEN_BASE_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-Base
TTS_QWEN_VOICE_DESIGN_MODEL=Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
TTS_QWEN_DTYPE=bfloat16
TTS_QWEN_ATTN=flash_attention_2

# VibeVoice: 4-bit quantized (fits in remaining VRAM)
TTS_VIBEVOICE_BASE_MODEL=DevParker/VibeVoice7b-low-vram
TTS_VIBEVOICE_DTYPE=float16
TTS_VIBEVOICE_QUANTIZATION=4bit
```

### Memory Usage

```
Qwen Base + VoiceDesign (bfloat16):     8GB
VibeVoice (4-bit quantized):            8GB
Working memory:                         4GB
────────────────────────────────────────────
Total:                                 20GB / 24GB ✅
Headroom:                               4GB
```

### Performance

**Sequential (single backend):**
- 20 lines: ~40 seconds

**Parallel (both backends):**
- 10 Qwen + 10 VibeVoice: ~50 seconds (1.25x faster)
- With batching: ~10 seconds (4x faster)

---

## Installation

### Qwen3-TTS

```bash
pip install qwen-tts>=0.0.5
pip install flash-attn --no-build-isolation  # Optional, recommended
```

### VibeVoice

```bash
# To be determined (official package pending)
# Current: Custom implementation in lib/backends/vibevoice.py
```

---

## References

### Qwen3-TTS
- **Model:** https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base
- **Paper:** https://arxiv.org/abs/2601.15621
- **GitHub:** https://github.com/QwenLM/Qwen3-TTS

### VibeVoice
- **Model:** https://huggingface.co/vibevoice/VibeVoice-7B
- **Quantized:** https://huggingface.co/DevParker/VibeVoice7b-low-vram
- **Paper:** https://arxiv.org/abs/2508.19205
- **GitHub:** https://github.com/microsoft/VibeVoice

---

**Last Updated:** 2026-02-04
