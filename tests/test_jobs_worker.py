"""Job worker lifecycle tests with a stubbed story generator."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import services.jobs as jobs_service


async def _wait_for(predicate, timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)


@pytest.fixture
async def worker(monkeypatch, fake_repos, clean_jobs_state):
    """Run the worker loop for the duration of a test, generation stubbed.

    Yields a dict the test can tweak: set ``gate`` to an asyncio.Event to make
    generation block until the event is set, or ``error`` to make it raise.
    """
    control: dict = {"gate": None, "error": None, "calls": 0}

    async def fake_generate_story(story_id, request_params):
        control["calls"] += 1
        if control["gate"] is not None:
            await control["gate"].wait()
        if control["error"] is not None:
            raise control["error"]
        return Path(f"/outputs/story/{story_id}/story_full.wav")

    monkeypatch.setattr(jobs_service, "generate_story", fake_generate_story)
    task = asyncio.create_task(jobs_service.process_job_queue())
    yield control
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_job_success_lifecycle(worker, fake_repos):
    job = await jobs_service.enqueue_story_job("template", {})
    assert job.status == "queued"

    await _wait_for(lambda: fake_repos.jobs.jobs.get(job.id) is not None)

    persisted = fake_repos.jobs.jobs[job.id]
    assert persisted.status == "succeeded"
    assert persisted.outputPath == "/outputs/story/template/story_full.wav"
    assert job.id not in jobs_service._active_jobs


async def test_job_failure_lifecycle(worker, fake_repos):
    worker["error"] = RuntimeError("sox exploded")

    job = await jobs_service.enqueue_story_job("template", {})
    await _wait_for(lambda: fake_repos.jobs.jobs.get(job.id) is not None)

    persisted = fake_repos.jobs.jobs[job.id]
    assert persisted.status == "failed"
    assert persisted.message == "sox exploded"


async def test_cancel_queued_job_never_runs(worker, fake_repos):
    worker["gate"] = asyncio.Event()  # block the worker on the first job
    blocker = await jobs_service.enqueue_story_job("other", {})
    await _wait_for(lambda: blocker.status == "running")

    job = await jobs_service.enqueue_story_job("template", {})
    cancelled = await jobs_service.cancel_job(job.id)

    assert cancelled is not None
    assert fake_repos.jobs.jobs[job.id].status == "failed"
    assert fake_repos.jobs.jobs[job.id].message == "Cancelled by user"

    worker["gate"].set()
    await _wait_for(lambda: fake_repos.jobs.jobs.get(blocker.id) is not None)
    # The cancelled job was skipped: generation ran only for the blocker.
    assert worker["calls"] == 1


async def test_cancel_running_job_result_is_discarded(worker, fake_repos):
    """Regression: a job cancelled while running must not be re-persisted as
    succeeded when its generation thread eventually completes."""
    worker["gate"] = asyncio.Event()

    job = await jobs_service.enqueue_story_job("template", {})
    await _wait_for(lambda: job.status == "running")

    cancelled = await jobs_service.cancel_job(job.id)
    assert cancelled is not None
    assert fake_repos.jobs.jobs[job.id].status == "failed"

    # Let the in-flight generation finish.
    worker["gate"].set()
    await _wait_for(lambda: not jobs_service._cancelled_ids)

    # The cancelled record must be the final word — no 'succeeded' overwrite.
    statuses = [j.status for j in fake_repos.jobs.save_history if j.id == job.id]
    assert statuses == ["failed"]
    assert fake_repos.jobs.jobs[job.id].status == "failed"


async def test_duplicate_enqueue_rejected(worker, fake_repos):
    worker["gate"] = asyncio.Event()
    await jobs_service.enqueue_story_job("template", {})

    with pytest.raises(ValueError, match="active_job"):
        await jobs_service.enqueue_story_job("template", {})

    worker["gate"].set()
