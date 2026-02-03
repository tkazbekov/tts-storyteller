"""Story routes."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, HTTPException

from lib.models import GenerateRequest, Job, ResolvedLine, StorySummary, StoryTemplate
from lib.repositories import get_story_repository, get_voice_repository
from lib.resolution import resolve_story
from lib.validation import validate_story
from services.jobs import cancel_job, enqueue_story_job, get_active_story_job

router = APIRouter()


@router.get("/stories")
async def list_stories_endpoint() -> list[StorySummary]:
    """
    List all stories.

    Returns story summaries with id, slug, and title.
    """
    story_repo = get_story_repository()
    story_ids = await story_repo.list_ids()

    summaries: list[StorySummary] = []
    for slug in story_ids:
        try:
            story = await story_repo.get(slug)
            summaries.append(
                StorySummary(
                    id=story.id,
                    slug=slug,
                    title=story.title,
                )
            )
        except KeyError:
            continue

    return summaries


@router.post("/stories", status_code=201)
async def create_story_endpoint(story: StoryTemplate) -> StoryTemplate:
    """
    Create a new story template.

    Voice assignment: Use the `casting` field to map roleIds (as strings) to voiceIds.
    Resolution order: line.actorId → casting[roleId] → defaultVoiceId

    Example casting: {"0": "narrator_male", "1": "woman"} assigns roleId 0 to narrator_male, roleId 1 to woman.

    Returns the story with server-generated `id` (UUID) and `slug` fields.
    """
    errors = validate_story(story.model_dump())
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    voice_repo = get_voice_repository()
    available_voices = await voice_repo.get_available_ids()
    if story.defaultVoiceId not in available_voices:
        raise HTTPException(
            status_code=400,
            detail=f"defaultVoiceId '{story.defaultVoiceId}' not found in available voices",
        )

    # Generate slug from title
    slug = re.sub(r"[^a-z0-9_-]", "", story.title.lower().replace(" ", "_"))
    if not slug:
        slug = "story"

    story_repo = get_story_repository()
    if await story_repo.exists(slug):
        raise HTTPException(status_code=409, detail=f"Story '{slug}' already exists")

    # Assign server-generated id and slug
    story.id = uuid.uuid4()
    story.slug = slug

    await story_repo.save(slug, story)
    return story


@router.get("/stories/{identifier}")
async def get_story_endpoint(identifier: str) -> StoryTemplate:
    """
    Get story template by ID or slug.

    The identifier can be either:
    - A UUID (e.g., "550e8400-e29b-41d4-a716-446655440000")
    - A slug (e.g., "my_story_title")
    """
    try:
        return await get_story_repository().get(identifier)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Story '{identifier}' not found") from None


@router.put("/stories/{storyId}")
async def replace_story_endpoint(storyId: str, story: StoryTemplate) -> StoryTemplate:
    """Replace an existing story template."""
    errors = validate_story(story.model_dump())
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    voice_repo = get_voice_repository()
    available_voices = await voice_repo.get_available_ids()
    if story.defaultVoiceId not in available_voices:
        raise HTTPException(
            status_code=400,
            detail=f"defaultVoiceId '{story.defaultVoiceId}' not found in available voices",
        )

    story_repo = get_story_repository()
    if not await story_repo.exists(storyId):
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found")

    # Preserve the existing id if not provided
    try:
        existing = await story_repo.get(storyId)
        if story.id is None:
            story.id = existing.id
        if story.slug is None:
            story.slug = existing.slug or storyId
    except KeyError:
        pass

    await story_repo.save(storyId, story)
    return story


@router.post("/stories/{storyId}/render")
async def render_story_endpoint(storyId: str) -> list[ResolvedLine]:
    """
    Resolve roles to voices for a story.

    Returns a preview of voice assignments showing which voice will be used for each line.
    Resolution order: line.actorId → casting[roleId] → defaultVoiceId

    Use this endpoint to verify voice assignments before generating audio.
    """
    story_repo = get_story_repository()
    try:
        story = await story_repo.get(storyId)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found") from None

    voice_repo = get_voice_repository()
    available_voices = await voice_repo.get_available_ids()

    try:
        resolved = resolve_story(story, available_voices)
        return resolved
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/stories/{storyId}/generate", status_code=202)
async def generate_story_endpoint(
    storyId: str,
    request: GenerateRequest | None = None,
    cancel_existing: bool = False,
) -> Job:
    """
    Start audio generation for a story.

    Only one job per story can be running or queued at a time.
    If a job is already active for this story, returns 409 Conflict unless
    cancel_existing=true, in which case the active job is cancelled and a new one is started.
    """
    story_repo = get_story_repository()
    if not await story_repo.exists(storyId):
        raise HTTPException(status_code=404, detail=f"Story '{storyId}' not found")

    existing_job = await get_active_story_job(storyId)
    if existing_job:
        if cancel_existing:
            await cancel_job(existing_job.id)
        else:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Job already active for story '{storyId}'. "
                    f"Existing job ID: {existing_job.id}, status: {existing_job.status}. "
                    "Wait for the current job to complete, cancel it (POST /jobs/{id}/cancel), "
                    "or retry with ?cancel_existing=true to cancel and start a new one."
                ),
            )

    request_params = request.model_dump() if request else {}

    try:
        job = await enqueue_story_job(storyId, request_params)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job already active for story '{storyId}'. "
                "Wait for the current job to complete or cancel it before starting a new one."
            ),
        ) from None

    return job
