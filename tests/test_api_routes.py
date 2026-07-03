"""Route tests against the FastAPI app with fake repositories.

The TestClient is used without entering its context manager, so the lifespan
(database init, worker startup) never runs — everything goes through the fake
repositories installed by the ``fake_repos`` fixture.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import services.jobs as jobs_service
from api.app import app
from lib.models import Job


@pytest.fixture
def client(fake_repos, clean_jobs_state):
    return TestClient(app)


STORY_BODY = {
    "schemaVersion": 1,
    "title": "Template",
    "defaultVoiceId": "narrator",
    "roles": [{"roleId": 0, "name": "Narrator"}],
    "lines": [{"id": 0, "roleId": 0, "line": "Hello there."}],
}


def _make_job(job_id: str, story_id: str, status: str) -> Job:
    return Job(
        id=job_id,
        type="generate",
        status=status,
        storyId=story_id,
        voiceId=None,
        message=None,
        outputPath=None,
        requestParams={},
        createdAt="2026-01-01T00:00:00+00:00",
        startedAt=None,
        finishedAt=None,
    )


def test_voices_pools_is_reachable(client, fake_repos):
    """Regression: /voices/pools must not be shadowed by /voices/{voiceId}."""
    fake_repos.pools.pools = {"fantasy": ["narrator"], "scifi": []}

    resp = client.get("/voices/pools")

    assert resp.status_code == 200
    assert resp.json() == ["fantasy", "scifi"]


def test_create_story(client, fake_repos):
    fake_repos.voices.voices["narrator"] = {"id": "narrator"}

    resp = client.post("/stories", json=STORY_BODY)

    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "template"
    assert body["id"] is not None


def test_create_story_duplicate_slug_conflict(client, fake_repos):
    fake_repos.voices.voices["narrator"] = {"id": "narrator"}
    assert client.post("/stories", json=STORY_BODY).status_code == 201

    resp = client.post("/stories", json=STORY_BODY)

    assert resp.status_code == 409


def test_voice_create_rejects_path_traversal_id(client, fake_repos):
    """Regression: voice ids flow into filesystem paths and must be restricted."""
    resp = client.post(
        "/voices",
        json={
            "id": "../../../../tmp/pwn",
            "language": "English",
            "instruction": "An evil voice",
            "sample_text": "Hello",
            "backend": "qwen",
        },
    )

    assert resp.status_code == 422


def test_voice_path_param_rejects_bad_id(client, fake_repos):
    resp = client.get("/voices/bad!id")

    assert resp.status_code == 422


def test_generate_rejects_cancel_existing_for_running_job(client, fake_repos):
    """A running job keeps writing to the story's output dir; replacing it
    mid-generation must be refused rather than double-writing."""
    fake_repos.stories.stories["template"] = None  # exists() only checks membership
    job = _make_job("job-1", "template", "running")
    jobs_service._active_jobs[job.id] = job

    resp = client.post("/stories/template/generate?cancel_existing=true")

    assert resp.status_code == 409
    assert "running" in resp.json()["detail"]


def test_generate_cancels_queued_job_and_enqueues_new_one(client, fake_repos):
    fake_repos.stories.stories["template"] = None
    job = _make_job("job-1", "template", "queued")
    jobs_service._active_jobs[job.id] = job

    resp = client.post("/stories/template/generate?cancel_existing=true")

    assert resp.status_code == 202
    new_job = resp.json()
    assert new_job["id"] != "job-1"
    # The old job was persisted as cancelled.
    cancelled = fake_repos.jobs.jobs["job-1"]
    assert cancelled.status == "failed"
    assert cancelled.message == "Cancelled by user"
