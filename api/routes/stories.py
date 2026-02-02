"""Story routes."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from lib.models import GenerateRequest, Job, ResolvedLine, StoryTemplate
from lib.resolution import resolve_story
from lib.storage import get_available_voice_ids, list_stories, load_story, save_story
from lib.validation import validate_story
from services.jobs import enqueue_story_job, get_active_story_job

router = APIRouter()


@router.get("/stories")
def list_stories_endpoint() -> list[str]:
    """List all story IDs."""
    return list_stories()


@router.post("/stories", status_code=201)
def create_story_endpoint(story: StoryTemplate) -> StoryTemplate:
    """
    Create a new story template.

    Voice assignment: Use the `casting` field to map roleIds (as strings) to voiceIds.
    Resolution order: line.actorId → casting[roleId] → defaultVoiceId

    Example casting: {"0": "narrator_male", "1": "woman"} assigns roleId 0 to narrator_male, roleId 1 to woman.
    """
    errors = validate_story(story.model_dump())
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    available_voices = get_available_voice_ids()
    if story.defaultVoiceId not in available_voices:
        raise HTTPException(
            status_code=400,
            detail=f"defaultVoiceId '{story.defaultVoiceId}' not found in available voices",
        )

    story_id = re.sub(r"[^a-z0-9_-]", "", story.title.lower().replace(" ", "_"))
    if not story_id:
        story_id = "story"

    try:
        load_story(story_id)
        raise HTTPException(status_code=409, detail=f"Story '{story_id}' already exists")
    except FileNotFoundError:
        pass

    save_story(story_id, story)
    return story


@router.get("/stories/{storyId}")
def get_story_endpoint(storyId: str) -> StoryTemplate:
    """Get story template by ID."""
    try:
        return load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None


@router.put("/stories/{storyId}")
def replace_story_endpoint(storyId: str, story: StoryTemplate) -> StoryTemplate:
    """Replace an existing story template."""
    errors = validate_story(story.model_dump())
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    available_voices = get_available_voice_ids()
    if story.defaultVoiceId not in available_voices:
        raise HTTPException(
            status_code=400,
            detail=f"defaultVoiceId '{story.defaultVoiceId}' not found in available voices",
        )

    try:
        load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None

    save_story(storyId, story)
    return story


@router.post("/stories/{storyId}/render")
def render_story_endpoint(storyId: str) -> list[ResolvedLine]:
    """
    Resolve roles to voices for a story.

    Returns a preview of voice assignments showing which voice will be used for each line.
    Resolution order: line.actorId → casting[roleId] → defaultVoiceId

    Use this endpoint to verify voice assignments before generating audio.
    """
    try:
        story = load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None

    available_voices = get_available_voice_ids()

    try:
        resolved = resolve_story(story, available_voices)
        return resolved
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/stories/{storyId}/generate", status_code=202)
def generate_story_endpoint(
    storyId: str,
    request: GenerateRequest | None = None,
) -> Job:
    """
    Start audio generation for a story.

    Only one job per story can be running or queued at a time.
    If a job is already active for this story, returns 409 Conflict.
    """
    try:
        load_story(storyId)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None

    existing_job = get_active_story_job(storyId)
    if existing_job:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job already active for story '{storyId}'. "
                f"Existing job ID: {existing_job.id}, status: {existing_job.status}. "
                "Wait for the current job to complete or cancel it before starting a new one."
            ),
        )

    request_params = request.model_dump() if request else {}

    try:
        job = enqueue_story_job(storyId, request_params)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job already active for story '{storyId}'. "
                "Wait for the current job to complete or cancel it before starting a new one."
            ),
        ) from None

    return job
