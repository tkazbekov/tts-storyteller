"""Voice routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lib.models import Voice, VoiceConfig
from lib.storage import (
    delete_voice_config,
    get_available_voice_ids,
    get_voice_info,
    get_voices_by_pool,
    load_voice_config,
    remove_voice_from_all_pools,
    save_voice_config,
    voice_has_prompt,
)
from lib.voice_metadata import should_regenerate_voice
from services.jobs import enqueue_voice_job, get_active_voice_job

router = APIRouter()


@router.get("/voices")
def list_voices(pool: str | None = None) -> list[Voice]:
    """
    List all available voices, optionally filtered by pool.

    Args:
        pool: Optional pool name to filter voices
    """
    if pool:
        voice_ids = set(get_voices_by_pool(pool))
    else:
        voice_ids = get_available_voice_ids()

    voices: list[Voice] = []
    for voice_id in sorted(voice_ids):
        info = get_voice_info(voice_id)
        if info:
            voices.append(Voice(**info))

    return voices


@router.get("/voices/{voiceId}")
def get_voice_endpoint(voiceId: str) -> Voice:
    """Get voice details by ID."""
    if not voice_has_prompt(voiceId):
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    info = get_voice_info(voiceId)
    if not info:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    return Voice(**info)


@router.post("/voices", status_code=202)
def create_voice_endpoint(voice_config: VoiceConfig):
    """
    Create a new voice.

    Generates WAV and prompt files, updates voices.json.
    Returns a job ID to track generation progress.
    """
    existing = load_voice_config(voice_config.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Voice '{voice_config.id}' already exists")

    if get_active_voice_job(voice_config.id):
        raise HTTPException(
            status_code=409,
            detail=f"Voice '{voice_config.id}' is already being generated",
        )

    try:
        job = enqueue_voice_job(voice_config.id, voice_config, "Queued for generation")
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=f"Voice '{voice_config.id}' is already being generated",
        ) from None

    return job


@router.put("/voices/{voiceId}")
def update_voice_endpoint(voiceId: str, voice_config: VoiceConfig):
    """
    Update an existing voice configuration.

    If config changed, triggers regeneration job.
    Otherwise, just updates voices.json.
    """
    existing = load_voice_config(voiceId)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    if voice_config.id != voiceId:
        raise HTTPException(status_code=400, detail="voiceId in path must match id in body")

    needs_regeneration = should_regenerate_voice(voiceId, voice_config)

    save_voice_config(voiceId, voice_config)

    if needs_regeneration:
        if get_active_voice_job(voiceId):
            raise HTTPException(
                status_code=409,
                detail=f"Voice '{voiceId}' is already being generated",
            )

        try:
            job = enqueue_voice_job(voiceId, voice_config, "Queued for regeneration")
        except ValueError:
            raise HTTPException(
                status_code=409,
                detail=f"Voice '{voiceId}' is already being generated",
            ) from None

        return job

    return voice_config


@router.delete("/voices/{voiceId}", status_code=204)
def delete_voice_endpoint(voiceId: str) -> None:
    """
    Delete a voice.

    Removes from voices.json and all pools.
    Does not delete WAV or prompt files.
    """
    existing = load_voice_config(voiceId)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    if get_active_voice_job(voiceId):
        raise HTTPException(
            status_code=409, detail=f"Voice '{voiceId}' is currently being generated"
        )

    delete_voice_config(voiceId)
    remove_voice_from_all_pools(voiceId)
