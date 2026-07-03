"""Job routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from lib.models import Job
from services.jobs import cancel_job, get_job, list_active_jobs, subscribe, unsubscribe

router = APIRouter()

_HEARTBEAT_SECONDS = 15.0


def _sse_event(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


@router.get("/jobs")
async def list_jobs_endpoint() -> list[Job]:
    """List active (queued/running) jobs. Use the Jobs UI to cancel if needed."""
    return list_active_jobs()


# Declared before /jobs/{jobId} so "events" isn't captured as a jobId
# (routes match in declaration order).
@router.get("/jobs/events", include_in_schema=False)
async def job_events_endpoint() -> StreamingResponse:
    """SSE stream of job transitions.

    Events:
    - `snapshot`: JSON array of active jobs, sent once on connect (also on
      every EventSource auto-reconnect, which is how clients self-heal)
    - `job`: full Job JSON on every transition, including terminal
      succeeded/failed states
    - `: keep-alive` comment roughly every 15s
    """

    async def stream() -> AsyncGenerator[str, None]:
        queue = subscribe()
        try:
            snapshot = json.dumps([j.model_dump(mode="json") for j in list_active_jobs()])
            yield _sse_event("snapshot", snapshot)
            while True:
                try:
                    job = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield _sse_event("job", job.model_dump_json())
        finally:
            # Starlette cancels this generator on client disconnect.
            unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            # no-transform: opt out of proxy/next-start compression buffering
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs/{jobId}")
async def get_job_endpoint(jobId: str) -> Job:
    """Get job status by ID."""
    job = await get_job(jobId)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{jobId}' not found")
    return job


@router.post("/jobs/{jobId}/cancel")
async def cancel_job_endpoint(jobId: str) -> Job:
    """
    Cancel an active (queued or running) job.
    Marks the job as failed with message 'Cancelled by user'.
    Returns 404 if job not found, 409 if job is not active (already finished).
    """
    job = await cancel_job(jobId)
    if not job:
        existing = await get_job(jobId)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Job '{jobId}' not found")
        raise HTTPException(
            status_code=409,
            detail=f"Job '{jobId}' is not active (status: {existing.status}). Only queued or running jobs can be cancelled.",
        )
    return job
