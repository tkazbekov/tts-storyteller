"""Incremental generation logic - compare stories and identify changed lines."""

import hashlib
from pathlib import Path

from lib.models import ResolvedLine
from lib.paths import get_story_output_dir


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
