"""Story generation orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from lib.generation import generate_story_audio
from lib.incremental import compute_line_hash
from lib.repositories import (
    get_metadata_repository,
    get_story_repository,
    get_voice_repository,
)
from lib.resolution import resolve_story
from services.models import get_base_model


async def _resolve_story(story_id: str):
    story_repo = get_story_repository()
    voice_repo = get_voice_repository()

    story = await story_repo.get(story_id)
    available_voices = await voice_repo.get_available_ids()
    resolved_lines = resolve_story(story, available_voices)
    return story, resolved_lines


async def generate_story(story_id: str, request_params: dict[str, Any] | None) -> Path:
    story, resolved_lines = await _resolve_story(story_id)
    language = story.language

    params = request_params or {}
    concat = params.get("concat", True)

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

    tts_model = get_base_model()

    output_path = await asyncio.to_thread(
        generate_story_audio,
        resolved_lines=resolved_lines,
        story_id=story_id,
        tts_model=tts_model,
        language=language,
        concat=concat,
        regenerate_indices=regenerate_indices,
    )

    await metadata_repo.save_line_hashes(story_id, current_hashes, language)
    return output_path
