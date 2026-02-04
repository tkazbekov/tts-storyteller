"""Abstract base class for TTS backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class VoicePrompt:
    """Generic voice prompt data structure.

    Each backend can store its own serialized data in the 'data' field.
    """

    backend: str  # e.g., "qwen", "vibevoice"
    voice_id: str
    data: dict[str, Any]  # Backend-specific serialized prompt


@dataclass
class AudioResult:
    """Result from TTS generation."""

    audio: np.ndarray  # Audio samples
    sample_rate: int  # Sample rate in Hz


class TTSBackend(ABC):
    """Abstract base class for TTS backend implementations."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Unique identifier for this backend (e.g., 'qwen', 'vibevoice')."""
        pass

    @abstractmethod
    def generate_voice_design(
        self, text: str, language: str, instruction: str, **kwargs: Any
    ) -> AudioResult:
        """Generate a designed voice from text description.

        Args:
            text: Sample text to synthesize
            language: Target language (e.g., "English", "Auto")
            instruction: Voice design instruction/description
            **kwargs: Backend-specific parameters

        Returns:
            AudioResult with generated audio
        """
        pass

    @abstractmethod
    def create_voice_clone_prompt(
        self, ref_audio: str | Path, ref_text: str | None, **kwargs: Any
    ) -> VoicePrompt:
        """Create reusable voice prompt from reference audio.

        Args:
            ref_audio: Path to reference audio file
            ref_text: Reference transcript (may be optional for some backends)
            **kwargs: Backend-specific parameters

        Returns:
            VoicePrompt that can be serialized and reused
        """
        pass

    @abstractmethod
    def generate_voice_clone(
        self, text: str, language: str, voice_prompt: VoicePrompt, **kwargs: Any
    ) -> AudioResult:
        """Generate speech using voice cloning.

        Args:
            text: Text to synthesize
            language: Target language
            voice_prompt: Voice prompt from create_voice_clone_prompt()
            **kwargs: Backend-specific parameters

        Returns:
            AudioResult with generated audio
        """
        pass

    @abstractmethod
    def save_prompt(self, prompt: VoicePrompt, path: str | Path) -> None:
        """Serialize and save voice prompt to disk.

        Args:
            prompt: Voice prompt to save
            path: Output file path
        """
        pass

    @abstractmethod
    def load_prompt(self, path: str | Path) -> VoicePrompt:
        """Load voice prompt from disk.

        Args:
            path: Path to prompt file

        Returns:
            Loaded VoicePrompt
        """
        pass
