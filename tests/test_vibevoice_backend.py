"""Tests for VibeVoice backend implementation."""

import json

import pytest

from lib.backends.base import VoicePrompt
from lib.backends.vibevoice import VibeVoiceBackend


@pytest.fixture
def vibevoice_backend():
    """Create VibeVoice backend instance (no model loading for tests)."""
    return VibeVoiceBackend(
        model_id="vibevoice/VibeVoice-1.5B",
        device="cpu",
        dtype="float32",
        quantization=None,
    )


def test_backend_name(vibevoice_backend):
    """Test backend name property."""
    assert vibevoice_backend.backend_name == "vibevoice"


def test_initialization():
    """Test backend initialization with various parameters."""
    backend = VibeVoiceBackend(
        model_id="vibevoice/VibeVoice-7B",
        device="cuda:0",
        dtype="float16",
        attn="flash_attention_2",
        quantization="4bit",
        cfg_scale=1.5,
        diffusion_steps=20,
    )

    assert backend.model_id == "vibevoice/VibeVoice-7B"
    assert backend.device == "cuda:0"
    assert backend.dtype == "float16"
    assert backend.attn == "flash_attention_2"
    assert backend.quantization == "4bit"
    assert backend.cfg_scale == 1.5
    assert backend.diffusion_steps == 20


def test_voice_design_not_supported(vibevoice_backend):
    """Test that voice design raises NotImplementedError."""
    with pytest.raises(NotImplementedError, match="voice design"):
        vibevoice_backend.generate_voice_design(
            text="Test",
            language="English",
            instruction="Test voice",
        )


def test_create_voice_clone_prompt_missing_file(vibevoice_backend):
    """Test that missing reference audio raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Reference audio not found"):
        vibevoice_backend.create_voice_clone_prompt(
            ref_audio="/nonexistent/path/audio.wav",
            ref_text="Test reference",
        )


def test_create_voice_clone_prompt(vibevoice_backend, tmp_path):
    """Test voice clone prompt creation."""
    # Create dummy WAV file
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_text("dummy wav content")

    prompt = vibevoice_backend.create_voice_clone_prompt(
        ref_audio=ref_audio,
        ref_text="Test reference",
    )

    assert prompt.backend == "vibevoice"
    assert prompt.data["ref_audio_path"] == str(ref_audio)
    assert prompt.data["ref_text"] == "Test reference"
    assert prompt.data["backend"] == "vibevoice"
    assert prompt.data["model_id"] == "vibevoice/VibeVoice-1.5B"


def test_create_voice_clone_prompt_no_ref_text(vibevoice_backend, tmp_path):
    """Test voice clone prompt creation without reference text."""
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_text("dummy wav content")

    prompt = vibevoice_backend.create_voice_clone_prompt(
        ref_audio=ref_audio,
        ref_text=None,
    )

    assert prompt.backend == "vibevoice"
    assert prompt.data["ref_text"] is None


def test_prompt_serialization(vibevoice_backend, tmp_path):
    """Test prompt save/load."""
    prompt = VoicePrompt(
        backend="vibevoice",
        voice_id="test_voice",
        data={
            "ref_audio_path": "/path/to/audio.wav",
            "ref_text": "Test",
            "backend": "vibevoice",
            "model_id": "vibevoice/VibeVoice-1.5B",
        },
    )

    prompt_path = tmp_path / "test_voice.json"
    vibevoice_backend.save_prompt(prompt, prompt_path)

    assert prompt_path.exists()

    # Verify JSON content
    with open(prompt_path) as f:
        saved_data = json.load(f)
    assert saved_data["backend"] == "vibevoice"
    assert saved_data["ref_audio_path"] == "/path/to/audio.wav"

    # Load and verify
    loaded = vibevoice_backend.load_prompt(prompt_path)
    assert loaded.backend == "vibevoice"
    assert loaded.voice_id == "test_voice"
    assert loaded.data["ref_audio_path"] == "/path/to/audio.wav"
    assert loaded.data["ref_text"] == "Test"


def test_load_prompt_invalid_backend(vibevoice_backend, tmp_path):
    """Test loading prompt with invalid backend raises ValueError."""
    prompt_path = tmp_path / "invalid.json"
    with open(prompt_path, "w") as f:
        json.dump({"backend": "qwen", "other": "data"}, f)

    with pytest.raises(ValueError, match="Invalid VibeVoice prompt file"):
        vibevoice_backend.load_prompt(prompt_path)


def test_load_prompt_missing_backend(vibevoice_backend, tmp_path):
    """Test loading prompt without backend field raises ValueError."""
    prompt_path = tmp_path / "missing.json"
    with open(prompt_path, "w") as f:
        json.dump({"some": "data"}, f)

    with pytest.raises(ValueError, match="Invalid VibeVoice prompt file"):
        vibevoice_backend.load_prompt(prompt_path)


def test_generate_voice_clone_wrong_backend(vibevoice_backend):
    """Test that wrong backend in prompt raises ValueError."""
    wrong_prompt = VoicePrompt(
        backend="qwen",
        voice_id="test",
        data={"ref_audio_path": "/some/path.wav"},
    )

    with pytest.raises(ValueError, match="Expected vibevoice prompt, got qwen"):
        vibevoice_backend.generate_voice_clone(
            text="Test",
            language="English",
            voice_prompt=wrong_prompt,
        )


def test_parse_dtype(vibevoice_backend):
    """Test dtype parsing."""
    import torch

    assert vibevoice_backend._parse_dtype("float16") == torch.float16
    assert vibevoice_backend._parse_dtype("fp16") == torch.float16
    assert vibevoice_backend._parse_dtype("float32") == torch.float32
    assert vibevoice_backend._parse_dtype("fp32") == torch.float32
    assert vibevoice_backend._parse_dtype("bfloat16") == torch.bfloat16
    assert vibevoice_backend._parse_dtype("bf16") == torch.bfloat16

    with pytest.raises(ValueError, match="Unsupported dtype"):
        vibevoice_backend._parse_dtype("invalid")


def test_prompt_subdirectory_creation(vibevoice_backend, tmp_path):
    """Test that save_prompt creates parent directories."""
    nested_path = tmp_path / "prompts" / "vibevoice" / "test.json"

    prompt = VoicePrompt(
        backend="vibevoice",
        voice_id="test",
        data={"backend": "vibevoice", "ref_audio_path": "/test.wav"},
    )

    vibevoice_backend.save_prompt(prompt, nested_path)

    assert nested_path.exists()
    assert nested_path.parent.exists()
