"""Job routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lib.models import Job
from services.jobs import cancel_job, get_job, list_active_jobs

router = APIRouter()


@router.get("/jobs")
async def list_jobs_endpoint() -> list[Job]:
    """List active (queued/running) jobs. Use the Jobs UI to cancel if needed."""
    return list_active_jobs()


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
