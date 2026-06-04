"""Factory for creating TTS backend instances."""

import os
from typing import Any

from lib.backends import TTSBackend
from lib.backends.qwen import QwenTTSBackend
from lib.backends.vibevoice import VibeVoiceBackend


class TTSBackendFactory:
    """Factory for creating and managing TTS backend instances."""

    _backends: dict[str, type[TTSBackend]] = {
        "qwen": QwenTTSBackend,
        "vibevoice": VibeVoiceBackend,
    }

    @classmethod
    def register_backend(cls, name: str, backend_class: type[TTSBackend]) -> None:
        """Register a new backend type.

        Args:
            name: Backend identifier (e.g., "vibevoice")
            backend_class: Backend class implementing TTSBackend
        """
        cls._backends[name] = backend_class

    @classmethod
    def create(cls, backend_type: str | None = None, **config: Any) -> TTSBackend:
        """Create a TTS backend instance.

        Args:
            backend_type: Backend type ("qwen", "vibevoice", etc.)
                         If None, reads from TTS_DEFAULT_BACKEND env var (default: "qwen")
            **config: Backend-specific configuration

        Returns:
            Initialized TTSBackend instance

        Raises:
            ValueError: If backend_type is unknown
        """
        if backend_type is None:
            backend_type = os.getenv("TTS_DEFAULT_BACKEND", "qwen")

        backend_class = cls._backends.get(backend_type)
        if backend_class is None:
            available = ", ".join(cls._backends.keys())
            raise ValueError(f"Unknown backend: {backend_type}. Available: {available}")

        return backend_class(**config)

    @classmethod
    def list_backends(cls) -> list[str]:
        """List all registered backend names."""
        return list(cls._backends.keys())
