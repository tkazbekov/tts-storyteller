"""Centralized path management using absolute paths based on project root."""

import os
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory (qwen3-tts)."""
    # Try environment variable first
    root = os.environ.get("QWEN3_TTS_ROOT")
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


def get_pools_config_path() -> Path:
    """Get the pools configuration JSON file path."""
    return get_voices_dir() / "pools.json"


def get_voice_metadata_path() -> Path:
    """Get the voice metadata JSON file path."""
    return get_voices_dir() / ".voice_metadata.json"


def get_voice_ref_audio_path(voice_id: str) -> Path:
    """Get the path to reference audio for a voice."""
    return get_voice_design_dir() / f"{voice_id}.wav"


def get_prompts_dir() -> Path:
    """Get the prompts directory path."""
    return PROJECT_ROOT / "prompts"


def get_outputs_dir() -> Path:
    """Get the outputs directory path."""
    return PROJECT_ROOT / "outputs"


def get_story_output_dir(story_id: str) -> Path:
    """Get the output directory for a specific story."""
    return PROJECT_ROOT / "outputs" / "story" / story_id


def get_voice_design_dir() -> Path:
    """Get the voice design output directory."""
    return PROJECT_ROOT / "outputs" / "voice_design"


def get_prompt_path(voice_id: str) -> Path:
    """Get the path to a prompt file for a voice."""
    return get_prompts_dir() / f"{voice_id}.pt"


def get_story_path(story_id: str) -> Path:
    """Get the path to a story JSON file."""
    return get_stories_dir() / f"{story_id}.json"


def get_story_full_audio_path(story_id: str) -> Path:
    """Get the path to the concatenated full story audio."""
    return get_story_output_dir(story_id) / "story_full.wav"
