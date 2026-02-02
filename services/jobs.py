"""Job queue and processor for async generation tasks."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from lib.models import Job, VoiceConfig
from lib.repositories import get_job_repository
from services.story_generation import generate_story
from services.voice_generation import generate_voice_job

_job_queue: asyncio.Queue[str] = asyncio.Queue()
_processing_job: str | None = None
_worker_task: asyncio.Task | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_job_id() -> str:
    return str(uuid.uuid4())


def get_job(job_id: str) -> Job | None:
    """Get a job by ID."""
    return get_job_repository().get(job_id)


def get_active_story_job(story_id: str) -> Job | None:
    """Get active (queued/running) job for a story."""
    return get_job_repository().get_active_for_story(story_id)


def get_active_voice_job(voice_id: str) -> Job | None:
    """Get active (queued/running) job for a voice."""
    return get_job_repository().get_active_for_voice(voice_id)


def enqueue_story_job(story_id: str, request_params: dict[str, Any] | None) -> Job:
    """Create and enqueue a story generation job."""
    job_repo = get_job_repository()

    if job_repo.get_active_for_story(story_id):
        raise ValueError("active_job")

    job = Job(
        id=_new_job_id(),
        type="generate",
        status="queued",
        storyId=story_id,
        voiceId=None,
        message="Job queued",
        outputPath=None,
        requestParams=request_params or {},
        createdAt=_now_iso(),
        startedAt=None,
        finishedAt=None,
    )

    job_repo.save(job)
    _job_queue.put_nowait(job.id)
    return job


def enqueue_voice_job(voice_id: str, voice_config: VoiceConfig, message: str) -> Job:
    """Create and enqueue a voice generation job."""
    job_repo = get_job_repository()

    if job_repo.get_active_for_voice(voice_id):
        raise ValueError("active_job")

    job = Job(
        id=_new_job_id(),
        type="voice_generate",
        status="queued",
        storyId=None,
        voiceId=voice_id,
        message=message,
        outputPath=None,
        requestParams={"voice_config": voice_config.model_dump()},
        createdAt=_now_iso(),
        startedAt=None,
        finishedAt=None,
    )

    job_repo.save(job)
    _job_queue.put_nowait(job.id)
    return job


def recover_jobs_on_startup() -> int:
    """
    Recover jobs from the database on startup.

    - Mark any "running" jobs as "failed" (server crashed while processing)
    - Re-queue any "queued" jobs

    Returns:
        Number of jobs recovered (re-queued)
    """
    job_repo = get_job_repository()

    # For database-backed repository, we can recover jobs
    # For in-memory repository, this is a no-op
    try:
        queued_jobs = job_repo.get_queued_jobs()
    except NotImplementedError:
        # In-memory repository doesn't persist jobs
        return 0

    recovered_count = 0

    for job in queued_jobs:
        # Check if this job was "running" (server crashed)
        if job.status == "running":
            job_repo.update_status(
                job.id,
                status="failed",
                message="Server restarted while job was running",
                finished_at=_now_iso(),
            )
            continue

        # Re-queue jobs that were still queued
        if job.status == "queued":
            _job_queue.put_nowait(job.id)
            recovered_count += 1

    return recovered_count


def start_worker() -> asyncio.Task:
    """Start the job processing worker."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(process_job_queue())
    return _worker_task


async def process_job_queue() -> None:
    """Process jobs from the queue (runs as a background task)."""
    global _processing_job

    job_repo = get_job_repository()

    while True:
        current_job: Job | None = None
        try:
            job_id = await _job_queue.get()
            _processing_job = job_id

            current_job = job_repo.get(job_id)
            if not current_job:
                _processing_job = None
                _job_queue.task_done()
                continue

            # Update job to running status
            started_at = _now_iso()
            message = (
                "Generating audio..."
                if current_job.storyId
                else "Generating voice..."
                if current_job.voiceId
                else "Processing..."
            )
            job_repo.update_status(
                job_id,
                status="running",
                message=message,
                started_at=started_at,
            )
            # Keep local object in sync
            current_job.status = "running"
            current_job.startedAt = started_at
            current_job.message = message

            if current_job.type == "voice_generate":
                if not current_job.voiceId:
                    raise ValueError("Job missing voiceId")

                request_params = current_job.requestParams or {}
                voice_config_dict = request_params.get("voice_config")
                if not voice_config_dict:
                    raise ValueError("Job missing voice_config in requestParams")

                voice_config = VoiceConfig(**voice_config_dict)
                prompt_path = await generate_voice_job(current_job.voiceId, voice_config)

                job_repo.update_status(
                    job_id,
                    status="succeeded",
                    message="Voice generation completed",
                    output_path=str(prompt_path),
                    finished_at=_now_iso(),
                )

            elif current_job.type == "generate":
                if not current_job.storyId:
                    raise ValueError("Job missing storyId")

                output_path = await generate_story(
                    current_job.storyId,
                    current_job.requestParams,
                )

                job_repo.update_status(
                    job_id,
                    status="succeeded",
                    message="Generation completed",
                    output_path=str(output_path),
                    finished_at=_now_iso(),
                )
            else:
                raise ValueError(f"Unknown job type: {current_job.type}")

        except Exception as e:
            if current_job:
                job_repo.update_status(
                    current_job.id,
                    status="failed",
                    message=str(e),
                    finished_at=_now_iso(),
                )
        finally:
            _processing_job = None
            if current_job is not None:
                _job_queue.task_done()
