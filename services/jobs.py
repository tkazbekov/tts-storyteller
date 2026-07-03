"""Job queue and processor for async generation tasks.

Active jobs (queued/running) live only in memory. The DB is used only for
history: we persist a job when it reaches a terminal state (succeeded, failed).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from lib.models import Job, VoiceCloneConfig, VoiceConfig
from lib.repositories import get_job_repository
from services.story_generation import generate_story
from services.voice_generation import generate_voice_clone_job, generate_voice_job

logger = logging.getLogger(__name__)

_job_queue: asyncio.Queue[str] = asyncio.Queue()
_active_jobs: dict[str, Job] = {}
_processing_job: str | None = None
# Jobs cancelled while running: the generation thread can't be killed, so the
# worker checks this set and discards the result instead of persisting it
# over the cancelled record.
_cancelled_ids: set[str] = set()
_worker_task: asyncio.Task | None = None
# Serializes the check-then-enqueue duplicate guard so two concurrent requests
# for the same story/voice can't both pass the "already active?" check.
_enqueue_lock = asyncio.Lock()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_job_id() -> str:
    return str(uuid.uuid4())


async def get_job(job_id: str) -> Job | None:
    """Get a job by ID (from memory if active, else from DB history)."""
    if job_id in _active_jobs:
        return _active_jobs[job_id]
    return await get_job_repository().get(job_id)


async def get_active_story_job(story_id: str) -> Job | None:
    """Get active (queued/running) job for a story. In-memory only."""
    for job in _active_jobs.values():
        if job.storyId == story_id and job.status in ("queued", "running"):
            return job
    return None


async def get_active_voice_job(voice_id: str) -> Job | None:
    """Get active (queued/running) job for a voice. In-memory only."""
    for job in _active_jobs.values():
        if job.voiceId == voice_id and job.status in ("queued", "running"):
            return job
    return None


def list_active_jobs() -> list[Job]:
    """List all active (queued/running) jobs. In-memory only."""
    return list(_active_jobs.values())


async def cancel_job(job_id: str) -> Job | None:
    """
    Mark an active (queued or running) job as failed with message 'Cancelled by user'.
    Persists to DB for history, then removes from active set.

    A running job's generation work cannot be interrupted mid-flight (it runs
    in a worker thread); it continues to completion but its result is discarded
    instead of being persisted over this cancelled record.
    """
    job = _active_jobs.get(job_id)
    if not job or job.status not in ("queued", "running"):
        return None
    if job.status == "running":
        _cancelled_ids.add(job_id)
    job.status = "failed"
    job.message = "Cancelled by user"
    job.finishedAt = _now_iso()
    await get_job_repository().save(job)
    del _active_jobs[job_id]
    return job


async def enqueue_story_job(story_id: str, request_params: dict[str, Any] | None) -> Job:
    """Create and enqueue a story generation job. Active state in memory only."""
    async with _enqueue_lock:
        if await get_active_story_job(story_id):
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
        _active_jobs[job.id] = job
        _job_queue.put_nowait(job.id)
        return job


async def enqueue_voice_job(voice_id: str, voice_config: VoiceConfig, message: str) -> Job:
    """Create and enqueue a voice generation job (voice design). Active state in memory only."""
    async with _enqueue_lock:
        if await get_active_voice_job(voice_id):
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
        _active_jobs[job.id] = job
        _job_queue.put_nowait(job.id)
        return job


async def enqueue_voice_clone_job(
    voice_id: str, voice_config: VoiceCloneConfig, message: str
) -> Job:
    """Create and enqueue a voice cloning job. Active state in memory only."""
    async with _enqueue_lock:
        if await get_active_voice_job(voice_id):
            raise ValueError("active_job")

        job = Job(
            id=_new_job_id(),
            type="voice_clone",
            status="queued",
            storyId=None,
            voiceId=voice_id,
            message=message,
            outputPath=None,
            requestParams={"voice_clone_config": voice_config.model_dump()},
            createdAt=_now_iso(),
            startedAt=None,
            finishedAt=None,
        )
        _active_jobs[job.id] = job
        _job_queue.put_nowait(job.id)
        return job


async def recover_jobs_on_startup() -> int:
    """
    On startup: mark any jobs still recorded as queued/running in the DB as
    failed (stale). We do not re-queue; active jobs live only in memory.

    Returns the number of stale jobs marked failed.
    """
    job_repo = get_job_repository()
    try:
        return await job_repo.mark_active_jobs_failed("Server restarted")
    except NotImplementedError:
        return 0


def start_worker() -> asyncio.Task:
    """Start the job processing worker."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(process_job_queue())
    return _worker_task


async def _persist_terminal(job: Job) -> None:
    """Persist a terminal job to history and drop it from the active set.

    Never raises: a DB failure here must not be allowed to kill the worker loop.
    """
    try:
        await get_job_repository().save(job)
    except Exception:
        logger.exception("Failed to persist terminal state for job %s", job.id)
    finally:
        _active_jobs.pop(job.id, None)


async def process_job_queue() -> None:
    """Process jobs from the queue (runs as a background task).

    The loop is defensive on purpose: any failure while handling a single job is
    logged and recorded on the job, then the loop moves on. Nothing a single job
    does (including a transient DB error) should be able to kill the worker and
    strand every subsequent job in the queue.
    """
    global _processing_job

    while True:
        job_id = await _job_queue.get()
        current_job: Job | None = None
        try:
            _processing_job = job_id

            current_job = _active_jobs.get(job_id)
            if not current_job or current_job.status != "queued":
                continue

            # Update to running (in memory only)
            current_job.status = "running"
            current_job.startedAt = _now_iso()
            current_job.message = (
                "Generating audio..."
                if current_job.storyId
                else "Generating voice..."
                if current_job.voiceId
                else "Processing..."
            )

            if current_job.type == "voice_generate":
                if not current_job.voiceId:
                    raise ValueError("Job missing voiceId")
                voice_config_dict = (current_job.requestParams or {}).get("voice_config")
                if not voice_config_dict:
                    raise ValueError("Job missing voice_config in requestParams")
                prompt_path = await generate_voice_job(
                    current_job.voiceId, VoiceConfig(**voice_config_dict)
                )
                current_job.message = "Voice generation completed"
                current_job.outputPath = str(prompt_path)

            elif current_job.type == "voice_clone":
                if not current_job.voiceId:
                    raise ValueError("Job missing voiceId")
                clone_config_dict = (current_job.requestParams or {}).get("voice_clone_config")
                if not clone_config_dict:
                    raise ValueError("Job missing voice_clone_config in requestParams")
                prompt_path = await generate_voice_clone_job(
                    current_job.voiceId, VoiceCloneConfig(**clone_config_dict)
                )
                current_job.message = "Voice cloning completed"
                current_job.outputPath = str(prompt_path)

            elif current_job.type == "generate":
                if not current_job.storyId:
                    raise ValueError("Job missing storyId")
                output_path = await generate_story(current_job.storyId, current_job.requestParams)
                current_job.message = "Generation completed"
                current_job.outputPath = str(output_path)

            else:
                raise ValueError(f"Unknown job type: {current_job.type}")

            if job_id in _cancelled_ids:
                # Cancelled while running: the cancel already persisted the
                # cancelled record; discard this result.
                _cancelled_ids.discard(job_id)
                logger.info("Job %s was cancelled while running; result discarded", job_id)
                continue

            current_job.status = "succeeded"
            current_job.finishedAt = _now_iso()
            await _persist_terminal(current_job)

        except Exception as e:
            logger.exception("Job %s failed", job_id)
            if job_id in _cancelled_ids or current_job is None:
                _cancelled_ids.discard(job_id)
            else:
                current_job.status = "failed"
                current_job.message = str(e)
                current_job.finishedAt = _now_iso()
                await _persist_terminal(current_job)
        finally:
            _processing_job = None
            _job_queue.task_done()
