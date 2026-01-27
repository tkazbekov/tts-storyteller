"""File-based storage utilities for stories, voices, and prompts."""

import json
from pathlib import Path
from typing import Any

from lib.models import StoryTemplate
from lib.paths import (
    get_prompt_path,
    get_prompts_dir,
    get_stories_dir,
    get_story_path,
    get_voices_config_path,
)


def load_story(story_id: str) -> StoryTemplate:
    """Load a story template from file."""
    path = get_story_path(story_id)
    if not path.exists():
        raise FileNotFoundError(f"Story '{story_id}' not found at {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return StoryTemplate(**data)


def save_story(story_id: str, story: StoryTemplate) -> None:
    """Save a story template to file."""
    path = get_story_path(story_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(story.model_dump(), f, indent=2)


def list_stories() -> list[str]:
    """List all story IDs (from JSON files in stories directory)."""
    stories_dir = get_stories_dir()
    if not stories_dir.exists():
        return []

    story_ids = []
    for path in stories_dir.glob("*.json"):
        story_ids.append(path.stem)

    return sorted(story_ids)


def load_voices_config() -> list[dict[str, Any]]:
    """Load the voices configuration JSON."""
    path = get_voices_config_path()
    if not path.exists():
        return []

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("voices.json must be a JSON array")

    return data


def get_available_voice_ids() -> set[str]:
    """Get set of available voice IDs (those with prompt files)."""
    prompts_dir = get_prompts_dir()
    if not prompts_dir.exists():
        return set()

    voice_ids = set()
    for path in prompts_dir.glob("*.pt"):
        voice_ids.add(path.stem)

    return voice_ids


def voice_has_prompt(voice_id: str) -> bool:
    """Check if a voice has a prompt file."""
    return get_prompt_path(voice_id).exists()


def get_voice_info(voice_id: str) -> dict[str, Any] | None:
    """
    Get voice information including prompt path and reference audio path.

    Returns None if voice not found.
    """
    voices = load_voices_config()
    for voice in voices:
        if voice.get("id") == voice_id:
            prompt_path = get_prompt_path(voice_id)
            info = {
                "id": voice_id,
                "promptPath": str(prompt_path) if prompt_path.exists() else None,
            }

            # Try to find reference audio
            ref_audio = voice.get("ref_audio")
            if not ref_audio:
                # Default location
                from lib.paths import get_voice_design_dir

                ref_audio_path = get_voice_design_dir() / f"{voice_id}.wav"
                if ref_audio_path.exists():
                    info["refAudioPath"] = str(ref_audio_path)
            else:
                ref_audio_path = Path(ref_audio)
                if ref_audio_path.exists():
                    info["refAudioPath"] = str(ref_audio_path)

            return info

    return None
