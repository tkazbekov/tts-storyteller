"""Voice pool routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lib.models import Voice, VoicePool
from lib.storage import (
    get_all_pools,
    get_available_voice_ids,
    get_voice_info,
    get_voices_by_pool,
    load_pools_config,
    save_pools_config,
)

router = APIRouter()


@router.get("/voices/pools")
def list_pools_endpoint() -> list[str]:
    """List all available voice pools."""
    return sorted(get_all_pools())


@router.get("/voices/pools/{poolName}")
def get_pool_endpoint(poolName: str) -> list[Voice]:
    """Get all voices in a pool."""
    voice_ids = get_voices_by_pool(poolName)
    if not voice_ids:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    voices: list[Voice] = []
    for voice_id in sorted(voice_ids):
        info = get_voice_info(voice_id)
        if info:
            voices.append(Voice(**info))

    return voices


@router.post("/voices/pools/{poolName}", status_code=201)
def create_pool_endpoint(poolName: str, pool: VoicePool) -> VoicePool:
    """Create a new pool."""
    if pool.name != poolName:
        raise HTTPException(status_code=400, detail="poolName in path must match name in body")

    pools = load_pools_config()
    if poolName in pools:
        raise HTTPException(status_code=409, detail=f"Pool '{poolName}' already exists")

    available_voices = get_available_voice_ids()
    for voice_id in pool.voiceIds:
        if voice_id not in available_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Voice '{voice_id}' not found in available voices",
            )

    pools[poolName] = pool.voiceIds
    save_pools_config(pools)

    return pool


@router.put("/voices/pools/{poolName}")
def update_pool_endpoint(poolName: str, pool: VoicePool) -> VoicePool:
    """Update an existing pool."""
    if pool.name != poolName:
        raise HTTPException(status_code=400, detail="poolName in path must match name in body")

    pools = load_pools_config()
    if poolName not in pools:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    available_voices = get_available_voice_ids()
    for voice_id in pool.voiceIds:
        if voice_id not in available_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Voice '{voice_id}' not found in available voices",
            )

    pools[poolName] = pool.voiceIds
    save_pools_config(pools)

    return pool


@router.delete("/voices/pools/{poolName}", status_code=204)
def delete_pool_endpoint(poolName: str) -> None:
    """Delete a pool."""
    pools = load_pools_config()
    if poolName not in pools:
        raise HTTPException(status_code=404, detail=f"Pool '{poolName}' not found")

    del pools[poolName]
    save_pools_config(pools)
