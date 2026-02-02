"""Model loading and caching for TTS services."""

from __future__ import annotations

import os

from qwen_tts import Qwen3TTSModel

from lib.runtime import load_tts_model


class ModelCache:
    """Cache for base and voice design models."""

    def __init__(self) -> None:
        self._base_model: Qwen3TTSModel | None = None
        self._voice_design_model: Qwen3TTSModel | None = None
        self._base_config: dict[str, str] = {
            "model": os.getenv("QWEN3_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-Base"),
            "device": os.getenv("QWEN3_TTS_DEVICE", "cuda:0"),
            "dtype": os.getenv("QWEN3_TTS_DTYPE", "bfloat16"),
            "attn": os.getenv("QWEN3_TTS_ATTN", "auto"),
        }
        self._voice_design_config: dict[str, str] = {
            "model": os.getenv(
                "QWEN3_TTS_VOICE_DESIGN_MODEL",
                "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            ),
            "device": os.getenv("QWEN3_TTS_DEVICE", "cuda:0"),
            "dtype": os.getenv("QWEN3_TTS_DTYPE", "bfloat16"),
            "attn": os.getenv("QWEN3_TTS_ATTN", "auto"),
        }

    def get_base_model(self) -> Qwen3TTSModel:
        if self._base_model is None:
            self._base_model = load_tts_model(
                self._base_config["model"],
                self._base_config["device"],
                self._base_config["dtype"],
                self._base_config["attn"],
            )
        return self._base_model

    def get_voice_design_model(self) -> Qwen3TTSModel:
        if self._voice_design_model is None:
            self._voice_design_model = load_tts_model(
                self._voice_design_config["model"],
                self._voice_design_config["device"],
                self._voice_design_config["dtype"],
                self._voice_design_config["attn"],
            )
        return self._voice_design_model


_model_cache = ModelCache()


def get_base_model() -> Qwen3TTSModel:
    return _model_cache.get_base_model()


def get_voice_design_model() -> Qwen3TTSModel:
    return _model_cache.get_voice_design_model()
