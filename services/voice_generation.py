"""Voice generation orchestration."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from lib.models import VoiceCloneConfig, VoiceConfig
from lib.paths import get_project_root, get_voice_ref_audio_path
from lib.repositories import get_voice_repository
from lib.voice_generation import generate_voice, generate_voice_prompt
from services.models import get_backend

# Reference audio for cloning must resolve inside this sandbox directory.
_UPLOADS_DIR = (get_project_root() / "uploads").resolve()


def resolve_reference_audio(ref_audio_url: str) -> Path:
    """Resolve a client-supplied ref_audio_url to a path inside the uploads sandbox.

    The only supported source is a file produced by POST /audio/upload, which
    lives under ``uploads/``. Anything resolving outside that directory is
    rejected so the API can't be pointed at arbitrary files on the host.

    Raises:
        ValueError: if the path escapes the uploads/ directory.
        FileNotFoundError: if the resolved file does not exist.
    """
    raw = Path(ref_audio_url)
    candidate = (raw if raw.is_absolute() else get_project_root() / raw).resolve()

    try:
        candidate.relative_to(_UPLOADS_DIR)
    except ValueError:
        raise ValueError(
            "ref_audio_url must point inside the uploads/ directory; "
            f"upload reference audio via POST /audio/upload first (got: {ref_audio_url})"
        ) from None

    if not candidate.exists():
        raise FileNotFoundError(f"Reference audio not found: {ref_audio_url}")

    return candidate


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

    # Resolve the client-supplied reference path inside the uploads sandbox.
    ref_audio_path = resolve_reference_audio(voice_config.ref_audio_url)

    # Generate prompt from reference audio
    prompt_path = await asyncio.to_thread(
        generate_voice_prompt,
        voice_id=voice_id,
        ref_audio_path=ref_audio_path,
        ref_text=voice_config.ref_text or "",
        tts_backend=base_backend,
        backend=backend_type,
    )

    # Keep a stable backend-specific reference WAV for API playback/UI previews.
    stored_ref_audio_path = get_voice_ref_audio_path(voice_id, backend_type)
    stored_ref_audio_path.parent.mkdir(parents=True, exist_ok=True)
    if ref_audio_path.resolve() != stored_ref_audio_path.resolve():
        shutil.copyfile(ref_audio_path, stored_ref_audio_path)

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
