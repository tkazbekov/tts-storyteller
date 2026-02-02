"""Story generation orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from lib.generation import generate_story_audio
from lib.metadata import find_changed_indices, load_line_hashes, save_line_hashes
from lib.resolution import resolve_story
from lib.storage import get_available_voice_ids, load_story
from services.models import get_base_model


def _resolve_story(story_id: str):
    story = load_story(story_id)
    available_voices = get_available_voice_ids()
    resolved_lines = resolve_story(story, available_voices)
    return story, resolved_lines


async def generate_story(story_id: str, request_params: dict[str, Any] | None) -> Path:
    story, resolved_lines = _resolve_story(story_id)
    language = story.language

    params = request_params or {}
    concat = params.get("concat", True)

    regenerate_indices: set[int] | None = None
    if load_line_hashes(story_id) is not None:
        regenerate_indices = find_changed_indices(story_id, resolved_lines, language)

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

    save_line_hashes(story_id, resolved_lines, language)
    return output_path
