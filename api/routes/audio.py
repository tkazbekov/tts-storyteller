"""Audio download routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from lib.paths import get_story_full_audio_path, get_story_output_dir

router = APIRouter()


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
