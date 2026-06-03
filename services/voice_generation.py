"""Voice generation orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path

from lib.models import VoiceCloneConfig, VoiceConfig
from lib.repositories import get_voice_repository
from lib.voice_generation import generate_voice, generate_voice_prompt
from services.models import get_backend


async def generate_voice_job(voice_id: str, voice_config: VoiceConfig) -> Path:
    """Generate voice using voice design (Qwen only).

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


async def generate_voice_clone_job(voice_id: str, voice_config: VoiceCloneConfig) -> Path:
    """Generate voice using voice cloning from reference audio (all backends).

    Args:
        voice_id: Voice identifier
        voice_config: Voice clone configuration including ref_audio_url

    Returns:
        Path to generated prompt file
    """
    backend_type = voice_config.backend

    # Get base backend for this backend type
    base_backend = get_backend(backend_type, "base")

    # Convert ref_audio_url to Path (assuming it's a local path for now)
    # TODO: Support downloading from URLs
    ref_audio_path = Path(voice_config.ref_audio_url)
    if not ref_audio_path.exists():
        raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")

    # Generate prompt from reference audio
    prompt_path = await asyncio.to_thread(
        generate_voice_prompt,
        voice_id=voice_id,
        ref_audio_path=ref_audio_path,
        ref_text=voice_config.ref_text or "",
        tts_backend=base_backend,
        backend=backend_type,
    )

    # Save voice config (convert to VoiceConfig format for storage)
    voice_config_for_storage = VoiceConfig(
        id=voice_id,
        language=voice_config.language,
        instruction=voice_config.instruction,
        sample_text=voice_config.ref_text or "",
        backend=backend_type,
    )
    await get_voice_repository().save(voice_id, voice_config_for_storage)

    return prompt_path
