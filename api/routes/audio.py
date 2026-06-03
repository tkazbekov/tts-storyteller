"""Audio download and upload routes."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from lib.paths import get_story_full_audio_path, get_story_output_dir, get_voice_ref_audio_path

router = APIRouter()

# Upload directory for reference audio files
UPLOAD_DIR = Path("uploads/reference_audio")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/audio/upload")
async def upload_reference_audio(file: UploadFile = File(...)) -> dict[str, str]:  # noqa: B008
    """
    Upload a reference audio file for voice cloning.

    Accepts WAV files. Returns the file path to use in ref_audio_url.

    Returns:
        {"file_path": "uploads/reference_audio/filename.wav"}
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(
            status_code=400,
            detail="Only WAV files are supported. Please upload a .wav file.",
        )

    # Save file
    file_path = UPLOAD_DIR / file.filename
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}",
        ) from e

    return {
        "file_path": str(file_path),
        "filename": file.filename,
        "message": f"File uploaded successfully. Use this path in ref_audio_url: {file_path}",
    }


@router.get("/audio/voices/{voiceId}.wav")
def get_voice_audio(voiceId: str) -> FileResponse:
    """
    Download the reference/sample audio for a voice.

    Returns 404 if the voice has not been generated yet (no WAV file).
    """
    audio_path = get_voice_ref_audio_path(voiceId)

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
def get_story_audio(storyId: str) -> FileResponse:
    """
    Download the concatenated audio file for a story.

    Note: This endpoint only works if the story was generated with `concat: true`.
    If `concat: false`, individual audio files are in the output directory but
    no concatenated file exists. Use `/audio/stories/{storyId}/files` to list individual files.
    """
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
def list_story_audio_files(storyId: str) -> list[str]:
    """
    List all individual audio files for a story.

    Returns a list of filenames in the story's output directory.
    These are the individual line audio files (e.g., "001_narrator_male.wav").
    """
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
def get_story_audio_file(storyId: str, filename: str) -> FileResponse:
    """
    Download a specific individual audio file for a story.

    Use GET /audio/stories/{storyId}/files to list available filenames.
    """
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
