"""TTS backend implementations."""

from lib.backends.base import AudioResult, TTSBackend, VoicePrompt
from lib.backends.qwen import QwenTTSBackend
from lib.backends.vibevoice import VibeVoiceBackend

__all__ = ["AudioResult", "TTSBackend", "VoicePrompt", "QwenTTSBackend", "VibeVoiceBackend"]
