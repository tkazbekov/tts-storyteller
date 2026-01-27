"""File-based storage utilities for stories, voices, and prompts."""

import json
from typing import Any

from lib.models import StoryTemplate, VoiceConfig
from lib.paths import (
    get_pools_config_path,
    get_prompt_path,
    get_prompts_dir,
    get_stories_dir,
    get_story_path,
    get_voice_ref_audio_path,
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


def load_voice_config(voice_id: str) -> dict[str, Any] | None:
    """Load a single voice config from voices.json."""
    voices = load_voices_config()
    for voice in voices:
        if voice.get("id") == voice_id:
            return voice
    return None


def save_voice_config(voice_id: str, voice_config: VoiceConfig) -> None:
    """
    Add or update a voice in voices.json.

    Args:
        voice_id: Voice identifier
        voice_config: Voice configuration
    """
    path = get_voices_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing voices
    voices = load_voices_config()

    # Find existing entry and update, or append new
    found = False
    voice_dict = voice_config.model_dump()
    for i, voice in enumerate(voices):
        if voice.get("id") == voice_id:
            voices[i] = voice_dict
            found = True
            break

    if not found:
        voices.append(voice_dict)

    # Save back to file
    with open(path, "w", encoding="utf-8") as f:
        json.dump(voices, f, indent=2)


def delete_voice_config(voice_id: str) -> None:
    """Remove a voice from voices.json."""
    path = get_voices_config_path()
    if not path.exists():
        return

    voices = load_voices_config()
    voices = [v for v in voices if v.get("id") != voice_id]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(voices, f, indent=2)


def get_voice_info(voice_id: str) -> dict[str, Any] | None:
    """
    Get voice information including prompt path and reference audio path.

    Returns None if voice not found.
    """
    voice_config = load_voice_config(voice_id)
    if not voice_config:
        return None

    prompt_path = get_prompt_path(voice_id)
    ref_audio_path = get_voice_ref_audio_path(voice_id)

    info = {
        "id": voice_id,
        "language": voice_config.get("language", "English"),
        "instruction": voice_config.get("instruction", ""),
        "sample_text": voice_config.get("sample_text"),
        "promptPath": str(prompt_path) if prompt_path.exists() else None,
        "refAudioPath": str(ref_audio_path) if ref_audio_path.exists() else None,
    }

    return info


def load_pools_config() -> dict[str, list[str]]:
    """Load the pools configuration JSON."""
    path = get_pools_config_path()
    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("pools.json must be a JSON object")

    return data


def save_pools_config(pools: dict[str, list[str]]) -> None:
    """Save the pools configuration JSON."""
    path = get_pools_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(pools, f, indent=2)


def get_voices_by_pool(pool_name: str) -> list[str]:
    """
    Get list of voice IDs in a pool.

    Args:
        pool_name: Pool name

    Returns:
        List of voice IDs in the pool, or empty list if pool doesn't exist
    """
    pools = load_pools_config()
    return pools.get(pool_name, [])


def get_all_pools() -> set[str]:
    """Get all pool names."""
    pools = load_pools_config()
    return set(pools.keys())


def add_voice_to_pool(voice_id: str, pool_name: str) -> None:
    """Add a voice to a pool."""
    pools = load_pools_config()
    if pool_name not in pools:
        pools[pool_name] = []
    if voice_id not in pools[pool_name]:
        pools[pool_name].append(voice_id)
    save_pools_config(pools)


def remove_voice_from_pool(voice_id: str, pool_name: str) -> None:
    """Remove a voice from a pool."""
    pools = load_pools_config()
    if pool_name in pools:
        pools[pool_name] = [vid for vid in pools[pool_name] if vid != voice_id]
        if not pools[pool_name]:
            # Remove empty pool
            del pools[pool_name]
        save_pools_config(pools)


def remove_voice_from_all_pools(voice_id: str) -> None:
    """Remove a voice from all pools."""
    pools = load_pools_config()
    updated = False
    for pool_name in list(pools.keys()):
        if voice_id in pools[pool_name]:
            pools[pool_name] = [vid for vid in pools[pool_name] if vid != voice_id]
            if not pools[pool_name]:
                del pools[pool_name]
            updated = True
    if updated:
        save_pools_config(pools)
