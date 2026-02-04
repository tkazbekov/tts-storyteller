"""Voice generation orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path

from lib.models import VoiceConfig
from lib.repositories import get_voice_repository
from lib.voice_generation import generate_voice
from services.models import get_backend


async def generate_voice_job(voice_id: str, voice_config: VoiceConfig) -> Path:
    """Generate voice with specified backend.

    Args:
        voice_id: Voice identifier
        voice_config: Voice configuration including backend

    Returns:
        Path to generated prompt file
    """
    backend_type = voice_config.backend

    # Get backend instances for this backend type
    voice_design_backend = get_backend(backend_type, "voice_design")
    base_backend = get_backend(backend_type, "base")

    wav_path, prompt_path = await asyncio.to_thread(
        generate_voice,
        voice_id=voice_id,
        voice_config=voice_config,
        voice_design_backend=voice_design_backend,
        base_backend=base_backend,
        force_regenerate=False,
    )

    await get_voice_repository().save(voice_id, voice_config)
    return prompt_path
