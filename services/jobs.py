"""Job queue and processor for async generation tasks."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from lib.models import Job, VoiceConfig
from services.story_generation import generate_story
from services.voice_generation import generate_voice_job

JOBS: dict[str, Job] = {}

_story_active_jobs: dict[str, str] = {}
_voice_active_jobs: dict[str, str] = {}

_job_queue: asyncio.Queue[str] = asyncio.Queue()
_processing_job: str | None = None
_worker_task: asyncio.Task | None = None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_job(job_id: str) -> Job | None:
    return JOBS.get(job_id)


def get_active_story_job(story_id: str) -> Job | None:
    job_id = _story_active_jobs.get(story_id)
    if not job_id:
        return None
    job = JOBS.get(job_id)
    if job and job.status in ("queued", "running"):
        return job
    return None


def get_active_voice_job(voice_id: str) -> Job | None:
    job_id = _voice_active_jobs.get(voice_id)
    if not job_id:
        return None
    job = JOBS.get(job_id)
    if job and job.status in ("queued", "running"):
        return job
    return None


def enqueue_story_job(story_id: str, request_params: dict[str, Any] | None) -> Job:
    if get_active_story_job(story_id):
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

    JOBS[job.id] = job
    _story_active_jobs[story_id] = job.id
    _job_queue.put_nowait(job.id)
    return job


def enqueue_voice_job(voice_id: str, voice_config: VoiceConfig, message: str) -> Job:
    if get_active_voice_job(voice_id):
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

    JOBS[job.id] = job
    _voice_active_jobs[voice_id] = job.id
    _job_queue.put_nowait(job.id)
    return job


def _new_job_id() -> str:
    import uuid

    return str(uuid.uuid4())


def start_worker() -> asyncio.Task:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(process_job_queue())
    return _worker_task


async def process_job_queue() -> None:
    global _processing_job

    while True:
        current_job: Job | None = None
        try:
            job_id = await _job_queue.get()
            _processing_job = job_id

            current_job = JOBS.get(job_id)
            if not current_job:
                _processing_job = None
                _job_queue.task_done()
                continue

            current_job.status = "running"
            current_job.startedAt = _now_iso()

            if current_job.storyId:
                _story_active_jobs[current_job.storyId] = job_id
                current_job.message = "Generating audio..."
            elif current_job.voiceId:
                _voice_active_jobs[current_job.voiceId] = job_id
                current_job.message = "Generating voice..."

            if current_job.type == "voice_generate":
                if not current_job.voiceId:
                    raise ValueError("Job missing voiceId")

                request_params = current_job.requestParams or {}
                voice_config_dict = request_params.get("voice_config")
                if not voice_config_dict:
                    raise ValueError("Job missing voice_config in requestParams")

                voice_config = VoiceConfig(**voice_config_dict)
                prompt_path = await generate_voice_job(current_job.voiceId, voice_config)

                current_job.status = "succeeded"
                current_job.message = "Voice generation completed"
                current_job.outputPath = str(prompt_path)

            elif current_job.type == "generate":
                if not current_job.storyId:
                    raise ValueError("Job missing storyId")

                output_path = await generate_story(
                    current_job.storyId,
                    current_job.requestParams,
                )

                current_job.status = "succeeded"
                current_job.message = "Generation completed"
                current_job.outputPath = str(output_path)
            else:
                raise ValueError(f"Unknown job type: {current_job.type}")

        except Exception as e:
            if current_job:
                current_job.status = "failed"
                current_job.message = str(e)
        finally:
            if current_job:
                current_job.finishedAt = _now_iso()
                if current_job.storyId and _story_active_jobs.get(current_job.storyId) == current_job.id:
                    _story_active_jobs.pop(current_job.storyId, None)
                if current_job.voiceId and _voice_active_jobs.get(current_job.voiceId) == current_job.id:
                    _voice_active_jobs.pop(current_job.voiceId, None)
            _processing_job = None
            if current_job is not None:
                _job_queue.task_done()
