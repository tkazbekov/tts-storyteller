"""Tests for TTS backend abstraction."""

import os
from unittest.mock import patch

import numpy as np
import pytest

from lib.backend_factory import TTSBackendFactory
from lib.backends import AudioResult, TTSBackend, VoicePrompt
from lib.backends.qwen import QwenTTSBackend
from lib.backends.vibevoice import VibeVoiceBackend


class TestBackendFactory:
    """Tests for TTSBackendFactory."""

    def test_factory_creates_qwen_backend(self):
        """Test that factory creates Qwen backend correctly."""
        with patch.dict(os.environ, {"TTS_DEFAULT_BACKEND": "qwen"}):
            backend = TTSBackendFactory.create(
                backend_type="qwen",
                model_id="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                device="cpu",
            )
            assert isinstance(backend, QwenTTSBackend)
            assert backend.backend_name == "qwen"
            assert backend.model_id == "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
            assert backend.device == "cpu"

    def test_factory_creates_vibevoice_backend(self):
        """Test that factory creates VibeVoice backend correctly."""
        backend = TTSBackendFactory.create(
            backend_type="vibevoice",
            model_id="default",
            device="cpu",
        )
        assert isinstance(backend, VibeVoiceBackend)
        assert backend.backend_name == "vibevoice"

    def test_factory_unknown_backend_raises(self):
        """Test that factory raises ValueError for unknown backend."""
        with pytest.raises(ValueError, match="Unknown backend: unknown"):
            TTSBackendFactory.create(backend_type="unknown")

    def test_factory_lists_backends(self):
        """Test that factory lists all registered backends."""
        backends = TTSBackendFactory.list_backends()
        assert "qwen" in backends
        assert "vibevoice" in backends
        assert len(backends) >= 2

    def test_factory_uses_env_var_default(self):
        """Test that factory uses TTS_DEFAULT_BACKEND env var as default."""
        with patch.dict(os.environ, {"TTS_DEFAULT_BACKEND": "qwen"}):
            backend = TTSBackendFactory.create(
                model_id="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                device="cpu",
            )
            assert isinstance(backend, QwenTTSBackend)

    def test_factory_register_backend(self):
        """Test that factory can register new backends."""

        class CustomBackend(TTSBackend):
            @property
            def backend_name(self) -> str:
                return "custom"

            def generate_voice_design(self, text, language, instruction, **kwargs):
                pass

            def create_voice_clone_prompt(self, ref_audio, ref_text, **kwargs):
                pass

            def generate_voice_clone(self, text, language, voice_prompt, **kwargs):
                pass

            def save_prompt(self, prompt, path):
                pass

            def load_prompt(self, path):
                pass

        TTSBackendFactory.register_backend("custom", CustomBackend)
        assert "custom" in TTSBackendFactory.list_backends()

        backend = TTSBackendFactory.create(backend_type="custom")
        assert isinstance(backend, CustomBackend)


class TestQwenBackend:
    """Tests for QwenTTSBackend."""

    def test_qwen_backend_initialization(self):
        """Test Qwen backend initialization."""
        backend = QwenTTSBackend(
            model_id="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device="cpu",
            dtype="float32",
            attn="none",
        )
        assert backend.backend_name == "qwen"
        assert backend.model_id == "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
        assert backend.device == "cpu"
        assert backend.dtype == "float32"
        assert backend.attn == "none"

    def test_parse_dtype(self):
        """Test dtype parsing."""
        torch = pytest.importorskip("torch", reason="requires a backend extra (torch)")

        from lib.backends._torch_utils import parse_dtype

        assert parse_dtype("bfloat16") == torch.bfloat16
        assert parse_dtype("bf16") == torch.bfloat16
        assert parse_dtype("float16") == torch.float16
        assert parse_dtype("fp16") == torch.float16
        assert parse_dtype("float32") == torch.float32
        assert parse_dtype("fp32") == torch.float32

        with pytest.raises(ValueError, match="Unsupported dtype"):
            parse_dtype("invalid")

    def test_detect_attn_impl(self):
        """Test attention implementation detection."""
        pytest.importorskip("torch", reason="requires a backend extra (torch)")

        from lib.backends._torch_utils import detect_attn_impl

        assert detect_attn_impl("none") is None
        assert detect_attn_impl("flash_attention_2") == "flash_attention_2"

        # Test auto detection (depends on flash_attn availability)
        result = detect_attn_impl("auto")
        assert result in [None, "flash_attention_2"]

        with pytest.raises(ValueError, match="attn must be one of"):
            detect_attn_impl("invalid")


class TestVibeVoiceBackend:
    """Tests for VibeVoiceBackend."""

    def test_vibevoice_backend_initialization(self):
        """Test VibeVoice backend initialization."""
        backend = VibeVoiceBackend(
            model_id="vibevoice/VibeVoice-1.5B",
            device="cpu",
            dtype="float32",
            quantization="4bit",
            cfg_scale=1.5,
            diffusion_steps=20,
        )
        assert backend.backend_name == "vibevoice"
        assert backend.model_id == "vibevoice/VibeVoice-1.5B"
        assert backend.device == "cpu"
        assert backend.dtype == "float32"
        assert backend.quantization == "4bit"
        assert backend.cfg_scale == 1.5
        assert backend.diffusion_steps == 20

    def test_vibevoice_methods_not_implemented(self):
        """Test that VibeVoice voice design is not supported."""
        backend = VibeVoiceBackend(model_id="default", device="cpu")

        # Voice design is not supported
        with pytest.raises(NotImplementedError, match="does not support voice design"):
            backend.generate_voice_design("text", "English", "instruction")


class TestDataClasses:
    """Tests for data classes."""

    def test_audio_result_creation(self):
        """Test AudioResult creation."""
        audio = np.array([0.1, 0.2, 0.3])
        result = AudioResult(audio=audio, sample_rate=16000)
        assert np.array_equal(result.audio, audio)
        assert result.sample_rate == 16000

    def test_voice_prompt_creation(self):
        """Test VoicePrompt creation."""
        prompt = VoicePrompt(
            backend="qwen",
            voice_id="narrator",
            data={"items": [{"test": "data"}]},
        )
        assert prompt.backend == "qwen"
        assert prompt.voice_id == "narrator"
        assert prompt.data == {"items": [{"test": "data"}]}


class TestBackendIntegration:
    """Integration tests for backend system."""

    def test_backend_interface_compliance(self):
        """Test that all backends implement the TTSBackend interface."""
        backends = [
            QwenTTSBackend(model_id="test", device="cpu", dtype="float32", attn="none"),
            VibeVoiceBackend(model_id="test", device="cpu"),
        ]

        for backend in backends:
            # Check that all required methods exist
            assert hasattr(backend, "backend_name")
            assert hasattr(backend, "generate_voice_design")
            assert hasattr(backend, "create_voice_clone_prompt")
            assert hasattr(backend, "generate_voice_clone")
            assert hasattr(backend, "save_prompt")
            assert hasattr(backend, "load_prompt")

            # Check that backend_name is a string
            assert isinstance(backend.backend_name, str)
            assert len(backend.backend_name) > 0
