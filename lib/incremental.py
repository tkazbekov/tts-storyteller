"""Incremental generation logic - compare stories and identify changed lines."""

import hashlib
from pathlib import Path

from lib.models import ResolvedLine, StoryTemplate
from lib.paths import get_story_output_dir
from lib.resolution import resolve_story


def compute_line_hash(resolved_line: ResolvedLine, language: str = "English") -> str:
    """
    Compute a hash for a resolved line to detect changes.

    A line is considered changed if:
    - The text changes
    - The voice ID changes
    - The language changes
    """
    # Create a stable string representation including language
    line_str = f"{resolved_line.voiceId}|{language}|{resolved_line.line}"
    return hashlib.sha256(line_str.encode()).hexdigest()[:16]


def find_changed_lines(
    old_story: StoryTemplate,
    new_story: StoryTemplate,
    available_voices: set[str],
) -> list[int]:
    """
    Compare two story templates and return indices (0-based) of lines that changed.

    A line is considered changed if:
    - The text changed
    - The voice assignment changed (due to actorId, casting, or defaultVoiceId changes)
    - The line was added/removed/reordered

    Args:
        old_story: Previous story template
        new_story: New story template
        available_voices: Set of available voice IDs

    Returns:
        List of 0-based line indices that need regeneration
    """
    # Resolve both stories to get actual voice assignments
    old_resolved = resolve_story(old_story, available_voices)
    new_resolved = resolve_story(new_story, available_voices)

    # Compute hashes for comparison
    old_hashes = [compute_line_hash(line) for line in old_resolved]
    new_hashes = [compute_line_hash(line) for line in new_resolved]

    # Find changed lines
    changed_indices: list[int] = []

    # Compare up to the minimum length
    min_len = min(len(old_hashes), len(new_hashes))
    for idx in range(min_len):
        if old_hashes[idx] != new_hashes[idx]:
            changed_indices.append(idx)

    # All lines beyond the old length are new/changed
    for idx in range(min_len, len(new_hashes)):
        changed_indices.append(idx)

    return changed_indices


def get_existing_audio_files(story_id: str) -> dict[int, Path]:
    """
    Get a mapping of line index (0-based) to existing audio file path.

    Returns:
        Dictionary mapping 0-based line index to Path of existing audio file,
        or empty dict if no files exist
    """
    output_dir = get_story_output_dir(story_id)
    if not output_dir.exists():
        return {}

    # Find all numbered WAV files (e.g., "001_narrator_male.wav")
    existing_files: dict[int, Path] = {}
    for wav_file in sorted(output_dir.glob("*.wav")):
        # Skip story_full.wav
        if wav_file.name == "story_full.wav":
            continue

        # Extract line number from filename (e.g., "001_narrator_male.wav" -> 1)
        try:
            # Filename format: "{idx:03d}_{voice_id}.wav"
            parts = wav_file.stem.split("_", 1)
            if parts:
                line_num = int(parts[0])
                # Convert to 0-based index
                existing_files[line_num - 1] = wav_file
        except (ValueError, IndexError):
            # Skip files that don't match the expected format
            continue

    return existing_files
