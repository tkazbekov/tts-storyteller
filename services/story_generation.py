"""Story generation orchestration with multi-backend parallel execution."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from lib.generation import generate_story_audio
from lib.incremental import compute_line_hash
from lib.models import ResolvedLine
from lib.repositories import (
    get_metadata_repository,
    get_story_repository,
    get_voice_repository,
)
from lib.resolution import resolve_story
from services.models import get_backend

logger = logging.getLogger(__name__)


async def _resolve_story(story_id: str):
    story_repo = get_story_repository()
    voice_repo = get_voice_repository()

    story = await story_repo.get(story_id)
    available_voices = await voice_repo.get_available_ids()
    resolved_lines = resolve_story(story, available_voices)
    return story, resolved_lines


async def _get_voice_backends(voice_ids: set[str]) -> dict[str, str]:
    """Get backend mapping for a set of voice IDs.

    Args:
        voice_ids: Set of voice IDs to look up

    Returns:
        Dictionary mapping voice_id -> backend_type
    """
    voice_repo = get_voice_repository()
    backend_map = {}

    for voice_id in voice_ids:
        try:
            voice = await voice_repo.get(voice_id)
            backend_map[voice_id] = voice.get("backend", "qwen") if voice else "qwen"
        except Exception:
            # Don't fail the whole story for one lookup; default to qwen but log it.
            logger.warning("Backend lookup failed for voice '%s'; defaulting to qwen", voice_id)
            backend_map[voice_id] = "qwen"

    return backend_map


def _group_lines_by_backend(
    resolved_lines: list[ResolvedLine],
    voice_backends: dict[str, str],
) -> dict[str, list[tuple[int, ResolvedLine]]]:
    """Group lines by their backend.

    Args:
        resolved_lines: List of resolved lines
        voice_backends: Mapping of voice_id -> backend_type

    Returns:
        Dictionary mapping backend_type -> list of (index, line) tuples
    """
    grouped: dict[str, list[tuple[int, ResolvedLine]]] = defaultdict(list)

    for idx, line in enumerate(resolved_lines):
        backend = voice_backends.get(line.voiceId, "qwen")
        grouped[backend].append((idx, line))

    return grouped


async def _generate_for_backend(
    backend_type: str,
    indexed_lines: list[tuple[int, ResolvedLine]],
    story_id: str,
    language: str,
    regenerate_indices: set[int] | None,
) -> list[tuple[int, Path]]:
    """Generate audio for lines using a specific backend.

    Args:
        backend_type: Backend to use (qwen, vibevoice)
        indexed_lines: List of (index, line) tuples to generate
        story_id: Story identifier
        language: Language for generation
        regenerate_indices: Set of indices to regenerate (None = all)

    Returns:
        List of (index, audio_path) tuples
    """
    if not indexed_lines:
        return []

    # Get backend instance
    backend = get_backend(backend_type, "base")

    # Extract just the lines (without indices) for generation
    lines_only = [line for _, line in indexed_lines]

    # Filter regenerate_indices to only include lines for this backend
    backend_regenerate_indices: set[int] | None = None
    if regenerate_indices is not None:
        line_indices = {idx for idx, _ in indexed_lines}
        backend_regenerate_indices = regenerate_indices & line_indices

    # Generate audio (this runs in a thread pool)
    await asyncio.to_thread(
        generate_story_audio,
        resolved_lines=lines_only,
        story_id=story_id,
        tts_backend=backend,
        language=language,
        concat=False,  # Don't concatenate per-backend, we'll do it globally
        regenerate_indices=backend_regenerate_indices,
    )

    # Map generated files back to original indices
    # generate_story_audio returns the output directory when concat=False
    from lib.paths import get_story_output_dir

    out_dir = get_story_output_dir(story_id)

    results: list[tuple[int, Path]] = []
    for _local_idx, (original_idx, line) in enumerate(indexed_lines):
        # Skip if we didn't regenerate this line
        if (
            backend_regenerate_indices is not None
            and original_idx not in backend_regenerate_indices
        ):
            # Check if existing file exists
            existing_file = out_dir / f"{original_idx + 1:03d}_{line.voiceId}.wav"
            if existing_file.exists():
                results.append((original_idx, existing_file))
            continue

        # Generated file path (1-based index)
        file_path = out_dir / f"{original_idx + 1:03d}_{line.voiceId}.wav"
        results.append((original_idx, file_path))

    return results


async def generate_story(story_id: str, request_params: dict[str, Any] | None) -> Path:
    """Generate story audio with parallel multi-backend execution.

    This function:
    1. Resolves voices to backends
    2. Groups lines by backend
    3. Executes generation in parallel for each backend
    4. Merges results and concatenates audio

    Args:
        story_id: Story identifier
        request_params: Optional generation parameters (concat, etc.)

    Returns:
        Path to concatenated audio file or output directory
    """
    story, resolved_lines = await _resolve_story(story_id)
    language = story.language

    params = request_params or {}
    concat = params.get("concat", True)

    # Compute incremental regeneration indices
    metadata_repo = get_metadata_repository()
    regenerate_indices: set[int] | None = None
    existing_metadata = await metadata_repo.load_line_hashes(story_id)
    current_hashes = [compute_line_hash(line, language) for line in resolved_lines]

    if existing_metadata is not None:
        previous_hashes, previous_language = existing_metadata
        if previous_language != language:
            regenerate_indices = set(range(len(resolved_lines)))
        else:
            changed_indices = {
                idx
                for idx in range(len(resolved_lines))
                if idx >= len(previous_hashes) or previous_hashes[idx] != current_hashes[idx]
            }
            regenerate_indices = changed_indices

    # Get voice backends
    voice_ids = {line.voiceId for line in resolved_lines}
    voice_backends = await _get_voice_backends(voice_ids)

    # Group lines by backend
    grouped_lines = _group_lines_by_backend(resolved_lines, voice_backends)

    # Check if we can use parallel execution
    if len(grouped_lines) > 1:
        # Parallel execution: multiple backends
        tasks = [
            _generate_for_backend(
                backend_type=backend_type,
                indexed_lines=indexed_lines,
                story_id=story_id,
                language=language,
                regenerate_indices=regenerate_indices,
            )
            for backend_type, indexed_lines in grouped_lines.items()
        ]

        # Execute in parallel
        results_per_backend = await asyncio.gather(*tasks)

        # Merge results from all backends
        all_results: list[tuple[int, Path]] = []
        for backend_results in results_per_backend:
            all_results.extend(backend_results)

        # Sort by index to get correct order
        all_results.sort(key=lambda x: x[0])

    else:
        # Single backend: use optimized path (no parallel overhead)
        backend_type = list(grouped_lines.keys())[0]
        tts_backend = get_backend(backend_type, "base")

        output_path = await asyncio.to_thread(
            generate_story_audio,
            resolved_lines=resolved_lines,
            story_id=story_id,
            tts_backend=tts_backend,
            language=language,
            concat=concat,
            regenerate_indices=regenerate_indices,
        )

        await metadata_repo.save_line_hashes(story_id, current_hashes, language)
        return output_path

    # Concatenate all audio files if requested
    if concat:
        import subprocess

        from lib.paths import get_story_full_audio_path, get_story_output_dir

        get_story_output_dir(story_id)
        output_files = [str(path) for _, path in all_results]

        sox_path = "sox"
        try:
            concat_out = get_story_full_audio_path(story_id)
            subprocess.run(
                [sox_path, *output_files, str(concat_out)],
                check=True,
                capture_output=True,
                text=True,
            )
            output_path = concat_out
        except FileNotFoundError as e:
            raise RuntimeError(f"{sox_path} not found. Install sox to enable concatenation.") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"sox concatenation failed: {e.stderr}") from e
    else:
        from lib.paths import get_story_output_dir

        output_path = get_story_output_dir(story_id)

    await metadata_repo.save_line_hashes(story_id, current_hashes, language)
    return output_path
