"""Audio download and upload routes."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi import Path as PathParam
from fastapi.responses import FileResponse

from lib.models import ID_PATTERN
from lib.paths import (
    get_project_root,
    get_story_full_audio_path,
    get_story_output_dir,
    get_voice_ref_audio_path,
)
from lib.repositories import get_voice_repository

router = APIRouter()

UPLOAD_DIR = get_project_root() / "uploads" / "reference_audio"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_upload_name(filename: str) -> str:
    stem = Path(filename).stem.strip() or "reference"
    suffix = Path(filename).suffix.lower()
    safe_stem = SAFE_FILENAME_RE.sub("_", stem).strip("._-") or "reference"
    return f"{safe_stem}-{uuid.uuid4().hex[:12]}{suffix}"


@router.post("/audio/upload")
async def upload_reference_audio(file: UploadFile = File(...)) -> dict[str, str]:  # noqa: B008
    """Upload a WAV reference clip for voice cloning.

    The file is stored under `uploads/reference_audio/` with a sanitized unique
    name. Use the returned `file_path` as `ref_audio_url` when cloning a voice.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    if Path(file.filename).suffix.lower() != ".wav":
        raise HTTPException(status_code=400, detail="Only WAV files are supported")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = _safe_upload_name(file.filename)
    file_path = UPLOAD_DIR / stored_name

    bytes_written = 0
    try:
        with file_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_BYTES:
                    buffer.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Reference audio is too large; max is {MAX_UPLOAD_BYTES // 1024 // 1024} MB",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}") from e
    finally:
        await file.close()

    relative_path = file_path.relative_to(get_project_root())
    return {
        "file_path": str(relative_path),
        "filename": stored_name,
        "original_filename": Path(file.filename).name,
        "message": f"File uploaded successfully. Use file_path as ref_audio_url: {relative_path}",
    }


@router.get("/audio/voices/{voiceId}.wav")
async def get_voice_audio(voiceId: str = PathParam(pattern=ID_PATTERN)) -> FileResponse:
    """Download the backend-specific reference/sample audio for a voice."""
    voice = await get_voice_repository().get(voiceId)
    backend = voice.get("backend", "qwen") if voice else "qwen"
    audio_path = get_voice_ref_audio_path(voiceId, backend)

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio for voice '{voiceId}' not found. Generate the voice first.",
        )

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"{voiceId}.wav",
    )


@router.get("/audio/stories/{storyId}/full.wav")
def get_story_audio(storyId: str = PathParam(pattern=ID_PATTERN)) -> FileResponse:
    """Download the concatenated audio file for a story."""
    audio_path = get_story_full_audio_path(storyId)

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio for story '{storyId}' not found. "
            "This endpoint requires the story to be generated with 'concat: true'. "
            "Check the job's outputPath for individual audio files location, "
            "or use GET /audio/stories/{storyId}/files to list available files.",
        )

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"{storyId}_full.wav",
    )


@router.get("/audio/stories/{storyId}/files")
def list_story_audio_files(storyId: str = PathParam(pattern=ID_PATTERN)) -> list[str]:
    """List all individual audio files for a story."""
    output_dir = get_story_output_dir(storyId)

    if not output_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Output directory for story '{storyId}' not found. "
            "The story may not have been generated yet.",
        )

    wav_files = sorted([f.name for f in output_dir.glob("*.wav")])

    if not wav_files:
        raise HTTPException(
            status_code=404,
            detail=f"No audio files found for story '{storyId}'.",
        )

    return wav_files


@router.get("/audio/stories/{storyId}/files/{filename}")
def get_story_audio_file(
    filename: str, storyId: str = PathParam(pattern=ID_PATTERN)
) -> FileResponse:
    """Download a specific individual audio file for a story."""
    output_dir = get_story_output_dir(storyId)
    audio_path = output_dir / filename

    try:
        audio_path.resolve().relative_to(output_dir.resolve())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filename: '{filename}'",
        ) from None

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Audio file '{filename}' not found for story '{storyId}'.",
        ) from None

    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=filename,
    )
