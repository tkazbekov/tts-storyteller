"""Voice pool routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lib.models import Voice, VoicePool
from lib.repositories import get_pool_repository, get_voice_repository

router = APIRouter()


@router.get("/voices/pools")
def list_pools_endpoint() -> list[str]:
    """List all available voice pools."""
    pool_repo = get_pool_repository()
    return sorted(pool_repo.list_pools())


@router.get("/voices/pools/{poolName}")
def get_pool_endpoint(poolName: str) -> list[Voice]:
    """Get all voices in a pool."""
    pool_repo = get_pool_repository()
    voice_ids = pool_repo.get_voices(poolName)
    if not voice_ids:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    voice_repo = get_voice_repository()
    voices: list[Voice] = []
    for voice_id in sorted(voice_ids):
        info = voice_repo.get_info(voice_id)
        if info:
            voices.append(Voice(**info))

    return voices


@router.post("/voices/pools/{poolName}", status_code=201)
def create_pool_endpoint(poolName: str, pool: VoicePool) -> VoicePool:
    """Create a new pool."""
    if pool.name != poolName:
        raise HTTPException(status_code=400, detail="poolName in path must match name in body")

    pool_repo = get_pool_repository()
    all_pools = pool_repo.get_all_pools()
    if poolName in all_pools:
        raise HTTPException(status_code=409, detail=f"Pool '{poolName}' already exists")

    voice_repo = get_voice_repository()
    available_voices = voice_repo.get_available_ids()
    for voice_id in pool.voiceIds:
        if voice_id not in available_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Voice '{voice_id}' not found in available voices",
            )

    pool_repo.save_pool(poolName, pool.voiceIds)

    return pool


@router.put("/voices/pools/{poolName}")
def update_pool_endpoint(poolName: str, pool: VoicePool) -> VoicePool:
    """Update an existing pool."""
    if pool.name != poolName:
        raise HTTPException(status_code=400, detail="poolName in path must match name in body")

    pool_repo = get_pool_repository()
    all_pools = pool_repo.get_all_pools()
    if poolName not in all_pools:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    voice_repo = get_voice_repository()
    available_voices = voice_repo.get_available_ids()
    for voice_id in pool.voiceIds:
        if voice_id not in available_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Voice '{voice_id}' not found in available voices",
            )

    pool_repo.save_pool(poolName, pool.voiceIds)

    return pool


@router.delete("/voices/pools/{poolName}", status_code=204)
def delete_pool_endpoint(poolName: str) -> None:
    """Delete a pool."""
    pool_repo = get_pool_repository()
    all_pools = pool_repo.get_all_pools()
    if poolName not in all_pools:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    pool_repo.delete_pool(poolName)
