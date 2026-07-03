"""Centralized path management using absolute paths based on project root."""

import os
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory (tts-storyteller)."""
    # Try new environment variable first, fall back to old one for backward compatibility
    root = os.environ.get("TTS_ROOT")
    if root:
        return Path(root).resolve()

    # Otherwise, detect from this file's location
    # This file is at lib/paths.py, so go up one level
    return Path(__file__).parent.parent.resolve()


PROJECT_ROOT = get_project_root()


def get_stories_dir() -> Path:
    """Get the stories directory path."""
    return PROJECT_ROOT / "stories"


def get_voices_dir() -> Path:
    """Get the voices directory path."""
    return PROJECT_ROOT / "voices"


def get_voices_config_path() -> Path:
    """Get the voices configuration JSON file path."""
    return get_voices_dir() / "voices.json"


def get_voice_metadata_path() -> Path:
    """Get the voice metadata JSON file path."""
    return get_voices_dir() / ".voice_metadata.json"


def get_voice_ref_audio_path(voice_id: str, backend: str = "qwen") -> Path:
    """Get the path to reference audio for a voice.

    Args:
        voice_id: Voice identifier
        backend: TTS backend (qwen, vibevoice)

    Returns:
        Path to reference audio file in backend subdirectory
    """
    return get_voice_design_dir() / backend / f"{voice_id}.wav"


def get_prompts_dir(backend: str | None = None) -> Path:
    """Get the prompts directory path.

    Args:
        backend: Optional backend subdirectory (qwen, vibevoice)

    Returns:
        Path to prompts directory or backend subdirectory
    """
    base = PROJECT_ROOT / "prompts"
    if backend:
        return base / backend
    return base


def get_story_output_dir(story_id: str) -> Path:
    """Get the output directory for a specific story."""
    return PROJECT_ROOT / "outputs" / "story" / story_id


def get_voice_design_dir(backend: str | None = None) -> Path:
    """Get the voice design output directory.

    Args:
        backend: Optional backend subdirectory (qwen, vibevoice)

    Returns:
        Path to voice_design directory or backend subdirectory
    """
    base = PROJECT_ROOT / "outputs" / "voice_design"
    if backend:
        return base / backend
    return base


# File extension used for each backend's serialized prompt files.
PROMPT_FILE_EXTENSIONS = {"qwen": ".pt", "vibevoice": ".json"}


def get_prompt_extension(backend: str) -> str:
    """Return the prompt-file extension for a backend (.pt for Qwen, .json otherwise)."""
    return PROMPT_FILE_EXTENSIONS.get(backend, ".json")


def get_prompt_path(voice_id: str, backend: str = "qwen") -> Path:
    """Get the path to a prompt file for a voice.

    Args:
        voice_id: Voice identifier
        backend: TTS backend (qwen, vibevoice)

    Returns:
        Path to prompt file with backend-specific extension
        - Qwen: .pt (PyTorch)
        - VibeVoice: .json
    """
    return get_prompts_dir(backend) / f"{voice_id}{get_prompt_extension(backend)}"


def get_story_full_audio_path(story_id: str) -> Path:
    """Get the path to the concatenated full story audio."""
    return get_story_output_dir(story_id) / "story_full.wav"


def ensure_backend_directories() -> None:
    """Ensure backend subdirectories exist for prompts and voice_design."""
    backends = ["qwen", "vibevoice"]
    for backend in backends:
        # Create prompts/backend/
        get_prompts_dir(backend).mkdir(parents=True, exist_ok=True)
        # Create outputs/voice_design/backend/
        get_voice_design_dir(backend).mkdir(parents=True, exist_ok=True)
