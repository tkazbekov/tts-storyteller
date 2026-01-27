"""Metadata storage for incremental generation - stores line hashes."""

import json
from pathlib import Path

from lib.incremental import compute_line_hash
from lib.models import ResolvedLine
from lib.paths import get_story_output_dir


def get_metadata_path(story_id: str) -> Path:
    """Get the path to the metadata file for a story."""
    return get_story_output_dir(story_id) / ".generation_metadata.json"


def save_line_hashes(story_id: str, resolved_lines: list[ResolvedLine], language: str) -> None:
    """
    Save line hashes to metadata file for future incremental generation.

    Args:
        story_id: Story identifier
        resolved_lines: List of resolved lines that were generated
        language: Language used for generation
    """
    metadata_path = get_metadata_path(story_id)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    # Compute hashes for all lines
    hashes = [compute_line_hash(line, language) for line in resolved_lines]

    metadata = {
        "line_count": len(resolved_lines),
        "language": language,
        "line_hashes": hashes,
    }

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def load_line_hashes(story_id: str) -> tuple[list[str], str] | None:
    """
    Load previously saved line hashes and language from metadata file.

    Args:
        story_id: Story identifier

    Returns:
        Tuple of (list of line hashes, language), or None if metadata doesn't exist
    """
    metadata_path = get_metadata_path(story_id)

    if not metadata_path.exists():
        return None

    try:
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
        hashes = metadata.get("line_hashes")
        language = metadata.get("language", "English")  # Default for old metadata files
        if hashes is None:
            return None
        return (hashes, language)
    except (json.JSONDecodeError, KeyError):
        return None


def find_changed_indices(
    story_id: str, resolved_lines: list[ResolvedLine], language: str
) -> set[int]:
    """
    Compare current resolved lines with previously saved hashes.

    Args:
        story_id: Story identifier
        resolved_lines: Current resolved lines to compare
        language: Current language for generation

    Returns:
        Set of 0-based line indices that need regeneration
    """
    metadata_result = load_line_hashes(story_id)

    if metadata_result is None:
        # No previous metadata - regenerate all
        return set(range(len(resolved_lines)))

    old_hashes, old_language = metadata_result

    # If language changed, regenerate all lines
    if old_language != language:
        print(
            f"[Incremental] Story '{story_id}': Language changed from '{old_language}' "
            f"to '{language}' - regenerating all lines"
        )
        return set(range(len(resolved_lines)))

    # Compute current hashes with current language
    current_hashes = [compute_line_hash(line, language) for line in resolved_lines]

    # Find changed indices
    changed_indices: set[int] = set()

    # Compare up to minimum length
    min_len = min(len(old_hashes), len(current_hashes))
    for idx in range(min_len):
        if old_hashes[idx] != current_hashes[idx]:
            changed_indices.add(idx)

    # All lines beyond old length are new
    for idx in range(min_len, len(current_hashes)):
        changed_indices.add(idx)

    # Debug: print comparison results
    print(
        f"[Incremental] Story '{story_id}': "
        f"{len(old_hashes)} old lines, {len(current_hashes)} current lines, "
        f"{len(changed_indices)} changed lines"
    )

    return changed_indices
