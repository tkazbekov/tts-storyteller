"""Centralized configuration for TTS backends."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class BackendConfig:
    """Configuration for a single TTS backend model."""

    model_id: str
    device: str = "cuda:0"
    dtype: str = "bfloat16"
    attn: str = "auto"

    # Backend-specific extras (API keys, quantization, etc.)
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSConfig:
    """Global TTS configuration loaded from environment variables."""

    # Default backend for new voices
    default_backend: Literal["qwen", "vibevoice"] = "qwen"

    # Shared device settings
    device: str = "cuda:0"

    # Qwen backend configs
    qwen_base: BackendConfig = field(
        default_factory=lambda: BackendConfig(
            model_id="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device="cuda:0",
            dtype="bfloat16",
            attn="flash_attention_2",
        )
    )

    qwen_voice_design: BackendConfig = field(
        default_factory=lambda: BackendConfig(
            model_id="Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            device="cuda:0",
            dtype="bfloat16",
            attn="flash_attention_2",
        )
    )

    # VibeVoice backend configs
    vibevoice_base: BackendConfig = field(
        default_factory=lambda: BackendConfig(
            model_id="DevParker/VibeVoice7b-low-vram",  # 4-bit quantized by default
            device="cuda:0",
            dtype="float16",
            attn="none",  # VibeVoice doesn't use FlashAttention
            extras={
                "quantization": "4bit",
                "cfg_scale": 3.0,
                "diffusion_steps": 50,
            },
        )
    )

    vibevoice_voice_design: BackendConfig = field(
        default_factory=lambda: BackendConfig(
            model_id="vibevoice/VibeVoice-Design-7B",  # If available
            device="cuda:0",
            dtype="float16",
            attn="none",
            extras={
                "quantization": "4bit",
            },
        )
    )

    @classmethod
    def from_env(cls) -> TTSConfig:
        """Load configuration from environment variables.

        Environment variable naming convention:
        - TTS_DEFAULT_BACKEND: Default backend for new voices
        - TTS_DEVICE: Shared device setting
        - TTS_<BACKEND>_<PURPOSE>_MODEL: Model ID
        - TTS_<BACKEND>_DTYPE: Data type
        - TTS_<BACKEND>_ATTN: Attention implementation
        - TTS_<BACKEND>_<PARAM>: Backend-specific parameters

        Examples:
        - TTS_QWEN_BASE_MODEL
        - TTS_QWEN_DTYPE
        - TTS_VIBEVOICE_BASE_MODEL
        - TTS_VIBEVOICE_QUANTIZATION
        - TTS_VIBEVOICE_API_KEY

        """
        device = os.getenv("TTS_DEVICE") or "cuda:0"

        return cls(
            default_backend=os.getenv("TTS_DEFAULT_BACKEND", "qwen"),  # type: ignore
            device=device,
            # Qwen base model
            qwen_base=BackendConfig(
                model_id=os.getenv("TTS_QWEN_BASE_MODEL") or "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                device=device,
                dtype=os.getenv("TTS_QWEN_DTYPE") or "bfloat16",
                attn=os.getenv("TTS_QWEN_ATTN") or "flash_attention_2",
                extras={
                    "max_new_tokens": int(os.getenv("TTS_QWEN_MAX_NEW_TOKENS", "2048")),
                    "top_p": float(os.getenv("TTS_QWEN_TOP_P", "0.95")),
                    "temperature": float(os.getenv("TTS_QWEN_TEMPERATURE", "1.0")),
                },
            ),
            # Qwen voice design model
            qwen_voice_design=BackendConfig(
                model_id=os.getenv("TTS_QWEN_VOICE_DESIGN_MODEL")
                or "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
                device=device,
                dtype=os.getenv("TTS_QWEN_DTYPE") or "bfloat16",
                attn=os.getenv("TTS_QWEN_ATTN") or "flash_attention_2",
            ),
            # VibeVoice base model
            vibevoice_base=BackendConfig(
                model_id=os.getenv("TTS_VIBEVOICE_BASE_MODEL")
                or "DevParker/VibeVoice7b-low-vram",  # 4-bit quantized default
                device=device,
                dtype=os.getenv("TTS_VIBEVOICE_DTYPE") or "float16",
                attn="none",  # VibeVoice doesn't use FlashAttention
                extras={
                    "quantization": os.getenv("TTS_VIBEVOICE_QUANTIZATION", "4bit"),
                    "cfg_scale": float(os.getenv("TTS_VIBEVOICE_CFG_SCALE", "3.0")),
                    "diffusion_steps": int(os.getenv("TTS_VIBEVOICE_DIFFUSION_STEPS", "50")),
                    "api_key": os.getenv("TTS_VIBEVOICE_API_KEY", ""),
                },
            ),
            # VibeVoice voice design (if available)
            vibevoice_voice_design=BackendConfig(
                model_id=os.getenv("TTS_VIBEVOICE_VOICE_DESIGN_MODEL")
                or "vibevoice/VibeVoice-Design-7B",
                device=device,
                dtype=os.getenv("TTS_VIBEVOICE_DTYPE") or "float16",
                attn="none",
                extras={
                    "quantization": os.getenv("TTS_VIBEVOICE_QUANTIZATION", "4bit"),
                },
            ),
        )

    def get_backend_config(self, backend: str, purpose: str = "base") -> BackendConfig:
        """Get configuration for a specific backend and purpose.

        Args:
            backend: Backend type ("qwen", "vibevoice")
            purpose: Model purpose ("base", "voice_design")

        Returns:
            BackendConfig for the specified backend and purpose

        Raises:
            ValueError: If backend or purpose is invalid
        """
        attr_name = f"{backend}_{purpose}"
        if not hasattr(self, attr_name):
            raise ValueError(
                f"Unknown backend/purpose: {backend}/{purpose}. "
                f"Available: qwen_base, qwen_voice_design, vibevoice_base, vibevoice_voice_design"
            )
        config: BackendConfig = getattr(self, attr_name)
        return config


# Global config instance (loaded once at startup)
_config: TTSConfig | None = None


def get_config() -> TTSConfig:
    """Get the global TTS configuration instance."""
    global _config
    if _config is None:
        _config = TTSConfig.from_env()
    return _config


def reload_config() -> TTSConfig:
    """Reload configuration from environment (useful for testing)."""
    global _config
    _config = TTSConfig.from_env()
    return _config
