"""Voice generation orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path

from lib.models import VoiceConfig
from lib.repositories import get_voice_repository
from lib.voice_generation import generate_voice
from services.models import get_base_model, get_voice_design_model


async def generate_voice_job(voice_id: str, voice_config: VoiceConfig) -> Path:
    voice_design_model = get_voice_design_model()
    base_model = get_base_model()

    wav_path, prompt_path = await asyncio.to_thread(
        generate_voice,
        voice_id=voice_id,
        voice_config=voice_config,
        voice_design_model=voice_design_model,
        base_model=base_model,
        force_regenerate=False,
    )

    await get_voice_repository().save(voice_id, voice_config)
    return prompt_path
