"""Model loading and caching for TTS services."""

from __future__ import annotations

from lib.backend_factory import TTSBackendFactory
from lib.backends import TTSBackend
from lib.config import get_config


class ModelCache:
    """Cache for multiple TTS backend instances."""

    def __init__(self) -> None:
        # Cache backends by (backend_type, purpose) tuple
        self._backends: dict[tuple[str, str], TTSBackend] = {}
        self._config = get_config()

    def get_backend(self, backend_type: str, purpose: str = "base") -> TTSBackend:
        """Get or create a backend instance.

        Args:
            backend_type: Backend type ("qwen", "vibevoice")
            purpose: Model purpose ("base", "voice_design")

        Returns:
            Cached or newly created TTSBackend instance

        Example:
            cache.get_backend("qwen", "base")        # Qwen base model
            cache.get_backend("qwen", "voice_design") # Qwen voice design
            cache.get_backend("vibevoice", "base")   # VibeVoice base
        """
        cache_key = (backend_type, purpose)

        if cache_key not in self._backends:
            # Get backend-specific config
            backend_config = self._config.get_backend_config(backend_type, purpose)

            # Create backend instance
            self._backends[cache_key] = TTSBackendFactory.create(
                backend_type=backend_type,
                model_id=backend_config.model_id,
                device=backend_config.device,
                dtype=backend_config.dtype,
                attn=backend_config.attn,
                **backend_config.extras,  # Pass extras (quantization, api_key, etc.)
            )

        return self._backends[cache_key]

    def clear_cache(self) -> None:
        """Clear all cached backends (useful for testing or memory management)."""
        self._backends.clear()

    def get_loaded_backends(self) -> list[tuple[str, str]]:
        """Get list of currently loaded backend (type, purpose) pairs."""
        return list(self._backends.keys())


# Singleton instance
_model_cache = ModelCache()


def get_backend(backend_type: str, purpose: str = "base") -> TTSBackend:
    """Get a TTS backend instance.

    Args:
        backend_type: Backend type ("qwen", "vibevoice")
        purpose: Model purpose ("base", "voice_design")

    Returns:
        TTSBackend instance
    """
    return _model_cache.get_backend(backend_type, purpose)


# Backward compatibility helpers
def get_base_backend() -> TTSBackend:
    """Get the default base backend (for backward compatibility)."""
    config = get_config()
    return _model_cache.get_backend(config.default_backend, "base")


def get_voice_design_backend() -> TTSBackend:
    """Get the default voice design backend (for backward compatibility)."""
    config = get_config()
    return _model_cache.get_backend(config.default_backend, "voice_design")
