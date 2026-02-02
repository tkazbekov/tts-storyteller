"""Job routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lib.models import Job
from services.jobs import get_job

router = APIRouter()


@router.get("/jobs/{jobId}")
def get_job_endpoint(jobId: str) -> Job:
    """Get job status by ID."""
    job = get_job(jobId)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{jobId}' not found")
    return job
