"""Voice routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi import Path as PathParam

from lib.models import ID_PATTERN, Voice, VoiceCloneConfig, VoiceConfig
from lib.repositories import get_pool_repository, get_voice_repository
from lib.voice_metadata import should_regenerate_voice
from services.jobs import enqueue_voice_clone_job, enqueue_voice_job, get_active_voice_job
from services.voice_generation import resolve_reference_audio

router = APIRouter()


@router.get("/voices")
async def list_voices(pool: str | None = None) -> list[Voice]:
    """
    List all available voices, optionally filtered by pool.

    Args:
        pool: Optional pool name to filter voices
    """
    voice_repo = get_voice_repository()

    if pool:
        pool_repo = get_pool_repository()
        voice_ids = set(await pool_repo.get_voices(pool))
    else:
        voice_ids = await voice_repo.get_available_ids()

    voices: list[Voice] = []
    for voice_id in sorted(voice_ids):
        info = await voice_repo.get_info(voice_id)
        if info:
            voices.append(Voice(**info))

    return voices


@router.get("/voices/{voiceId}")
async def get_voice_endpoint(voiceId: str = PathParam(pattern=ID_PATTERN)) -> Voice:
    """Get voice details by ID."""
    voice_repo = get_voice_repository()

    if not await voice_repo.has_prompt(voiceId):
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    info = await voice_repo.get_info(voiceId)
    if not info:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    return Voice(**info)


@router.post("/voices", status_code=202)
async def create_voice_endpoint(voice_config: VoiceConfig):
    """
    Create a new voice using voice design (Qwen only).

    Generates voice from text description. Not supported for VibeVoice backend.
    For VibeVoice, use POST /voices/clone instead.

    Generates WAV and prompt files and saves the voice to the database.
    Returns a job ID to track generation progress.
    """
    if voice_config.backend != "qwen":
        raise HTTPException(
            status_code=400,
            detail=f"Voice design is only supported for 'qwen' backend. "
            f"For '{voice_config.backend}' backend, use POST /voices/clone with reference audio.",
        )

    voice_repo = get_voice_repository()
    existing = await voice_repo.get(voice_config.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Voice '{voice_config.id}' already exists")

    if await get_active_voice_job(voice_config.id):
        raise HTTPException(
            status_code=409,
            detail=f"Voice '{voice_config.id}' is already being generated",
        )

    try:
        job = await enqueue_voice_job(voice_config.id, voice_config, "Queued for generation")
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=f"Voice '{voice_config.id}' is already being generated",
        ) from None

    return job


@router.post("/voices/clone", status_code=202)
async def clone_voice_endpoint(voice_config: VoiceCloneConfig):
    """
    Create a new voice using voice cloning from reference audio.

    Works with all backends (qwen, vibevoice). Requires reference audio file.
    Generates a prompt from the reference audio and saves the voice to the database.
    Returns a job ID to track generation progress.
    """
    try:
        resolve_reference_audio(voice_config.ref_audio_url)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    voice_repo = get_voice_repository()
    existing = await voice_repo.get(voice_config.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Voice '{voice_config.id}' already exists")

    if await get_active_voice_job(voice_config.id):
        raise HTTPException(
            status_code=409,
            detail=f"Voice '{voice_config.id}' is already being generated",
        )

    try:
        job = await enqueue_voice_clone_job(
            voice_config.id, voice_config, "Queued for voice cloning"
        )
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=f"Voice '{voice_config.id}' is already being generated",
        ) from None

    return job


@router.put("/voices/{voiceId}")
async def update_voice_endpoint(
    voice_config: VoiceConfig, voiceId: str = PathParam(pattern=ID_PATTERN)
):
    """
    Update an existing voice configuration.

    If config changed, triggers regeneration job.
    Otherwise, just saves the updated configuration.
    """
    voice_repo = get_voice_repository()
    existing = await voice_repo.get(voiceId)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    if voice_config.id != voiceId:
        raise HTTPException(status_code=400, detail="voiceId in path must match id in body")

    needs_regeneration = should_regenerate_voice(voiceId, voice_config)

    await voice_repo.save(voiceId, voice_config)

    if needs_regeneration:
        if await get_active_voice_job(voiceId):
            raise HTTPException(
                status_code=409,
                detail=f"Voice '{voiceId}' is already being generated",
            )

        try:
            job = await enqueue_voice_job(voiceId, voice_config, "Queued for regeneration")
        except ValueError:
            raise HTTPException(
                status_code=409,
                detail=f"Voice '{voiceId}' is already being generated",
            ) from None

        return job

    return voice_config


@router.delete("/voices/{voiceId}", status_code=204)
async def delete_voice_endpoint(voiceId: str = PathParam(pattern=ID_PATTERN)) -> None:
    """
    Delete a voice.

    Removes the voice from the database and all pools.
    Does not delete WAV or prompt files.
    """
    voice_repo = get_voice_repository()
    existing = await voice_repo.get(voiceId)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Voice '{voiceId}' not found")

    if await get_active_voice_job(voiceId):
        raise HTTPException(
            status_code=409, detail=f"Voice '{voiceId}' is currently being generated"
        )

    await voice_repo.delete(voiceId)
    pool_repo = get_pool_repository()
    await pool_repo.remove_voice_from_all(voiceId)
