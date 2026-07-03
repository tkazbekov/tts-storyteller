"""Tests for the /jobs/events SSE stream and its publish/subscribe plumbing."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import uvicorn

import services.jobs as jobs_service
from api.app import app


async def _wait_for(predicate, timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)


@pytest.fixture
async def worker(monkeypatch, fake_repos, clean_jobs_state):
    """Same stubbed-generator worker harness as test_jobs_worker.py."""
    control: dict = {"gate": None, "error": None}

    async def fake_generate_story(story_id, request_params):
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


async def test_publish_subscribe_lifecycle(worker):
    queue = jobs_service.subscribe()
    try:
        job = await jobs_service.enqueue_story_job("template", {})

        queued = await asyncio.wait_for(queue.get(), timeout=5)
        assert queued.id == job.id
        assert queued.status == "queued"

        running = await asyncio.wait_for(queue.get(), timeout=5)
        assert running.status == "running"

        succeeded = await asyncio.wait_for(queue.get(), timeout=5)
        assert succeeded.status == "succeeded"

        # Deep-copy regression: earlier snapshots must not have been mutated
        # by later transitions of the same underlying Job object.
        assert queued.status == "queued"
        assert running.status == "running"
    finally:
        jobs_service.unsubscribe(queue)


async def test_cancel_publishes_exactly_one_terminal_event(worker, fake_repos):
    worker["gate"] = asyncio.Event()
    job = await jobs_service.enqueue_story_job("template", {})
    await _wait_for(lambda: job.status == "running")

    queue = jobs_service.subscribe()
    try:
        await jobs_service.cancel_job(job.id)

        cancelled = await asyncio.wait_for(queue.get(), timeout=5)
        assert cancelled.id == job.id
        assert cancelled.status == "failed"
        assert cancelled.message == "Cancelled by user"

        # Let the in-flight generation finish; its result is discarded and
        # must NOT produce a second event for this job.
        worker["gate"].set()
        await _wait_for(lambda: not jobs_service._cancelled_ids)
        assert queue.empty()
    finally:
        jobs_service.unsubscribe(queue)


@pytest.fixture
async def live_server():
    """Real uvicorn on an ephemeral port.

    httpx's ASGITransport runs the app to completion before returning the
    response, which never happens for an infinite SSE stream — streaming
    tests need a real socket. lifespan="off" skips DB init and the app's own
    worker startup (tests drive their own worker task).
    """
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", lifespan="off")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    await _wait_for(lambda: server.started)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    await asyncio.wait_for(task, timeout=5)


def _parse_sse_frames(lines: list[str]) -> list[tuple[str, dict | list]]:
    """Parse accumulated SSE lines into (event, parsed-json) tuples."""
    frames: list[tuple[str, dict | list]] = []
    event: str | None = None
    data: list[str] = []
    for line in lines:
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data.append(line.removeprefix("data:").strip())
        elif line == "" and event is not None:
            frames.append((event, json.loads("\n".join(data))))
            event, data = None, []
    return frames


async def test_events_endpoint_streams_transitions(worker, live_server):
    async with httpx.AsyncClient(base_url=live_server) as client:
        async with client.stream("GET", "/jobs/events") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")

            lines: list[str] = []
            frames: list[tuple[str, dict | list]] = []
            enqueued = False
            async with asyncio.timeout(10):
                async for line in resp.aiter_lines():
                    lines.append(line)
                    frames = _parse_sse_frames(lines)
                    if frames and not enqueued:
                        # First frame is the (empty) snapshot; now make noise.
                        assert frames[0] == ("snapshot", [])
                        await jobs_service.enqueue_story_job("template", {})
                        enqueued = True
                    statuses = [f[1]["status"] for f in frames if f[0] == "job"]
                    if "succeeded" in statuses:
                        break

            statuses = [f[1]["status"] for f in frames if f[0] == "job"]
            assert statuses == ["queued", "running", "succeeded"]

    # Disconnect propagation is async: the subscriber must get cleaned up.
    await _wait_for(lambda: not jobs_service._subscribers)


async def test_snapshot_contains_preseeded_active_jobs(worker, live_server):
    # Gate the worker so the job is still active when the snapshot is taken.
    worker["gate"] = asyncio.Event()
    job = await jobs_service.enqueue_story_job("template", {})

    async with httpx.AsyncClient(base_url=live_server) as client:
        async with client.stream("GET", "/jobs/events") as resp:
            lines: list[str] = []
            async with asyncio.timeout(10):
                async for line in resp.aiter_lines():
                    lines.append(line)
                    frames = _parse_sse_frames(lines)
                    if frames:
                        event, payload = frames[0]
                        assert event == "snapshot"
                        assert isinstance(payload, list)
                        assert job.id in [j["id"] for j in payload]
                        break
