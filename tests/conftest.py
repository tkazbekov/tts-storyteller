"""Shared test fixtures: in-memory repository fakes and jobs-state cleanup.

Routes call ``get_*_repository()`` (from ``lib.repositories.factory``) at
request time, so installing fakes into the factory's singleton slots swaps the
persistence layer for the whole app without a database.
"""

from __future__ import annotations

from typing import Any

import pytest

import lib.repositories.factory as repo_factory
import services.jobs as jobs_service
from lib.models import Job, StoryTemplate, VoiceConfig


class FakeStoryRepository:
    def __init__(self) -> None:
        self.stories: dict[str, StoryTemplate] = {}

    async def get(self, story_id: str) -> StoryTemplate:
        if story_id not in self.stories:
            raise KeyError(f"Story '{story_id}' not found")
        return self.stories[story_id]

    async def list_ids(self) -> list[str]:
        return sorted(self.stories)

    async def save(self, story_id: str, story: StoryTemplate) -> None:
        self.stories[story_id] = story

    async def exists(self, story_id: str) -> bool:
        return story_id in self.stories

    async def delete(self, story_id: str) -> None:
        self.stories.pop(story_id, None)


class FakeVoiceRepository:
    def __init__(self) -> None:
        self.voices: dict[str, dict[str, Any]] = {}

    async def get(self, voice_id: str) -> dict[str, Any] | None:
        return self.voices.get(voice_id)

    async def get_info(self, voice_id: str) -> dict[str, Any] | None:
        return self.voices.get(voice_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self.voices.values())

    async def save(self, voice_id: str, voice_config: VoiceConfig) -> None:
        self.voices[voice_id] = voice_config.model_dump()

    async def delete(self, voice_id: str) -> None:
        self.voices.pop(voice_id, None)

    async def get_available_ids(self) -> set[str]:
        return set(self.voices)

    async def has_prompt(self, voice_id: str) -> bool:
        return voice_id in self.voices


class FakePoolRepository:
    def __init__(self) -> None:
        self.pools: dict[str, list[str]] = {}

    async def get_voices(self, pool_name: str) -> list[str]:
        return self.pools.get(pool_name, [])

    async def list_pools(self) -> set[str]:
        return set(self.pools)

    async def get_all_pools(self) -> dict[str, list[str]]:
        return dict(self.pools)

    async def save_pool(self, pool_name: str, voice_ids: list[str]) -> None:
        self.pools[pool_name] = list(voice_ids)

    async def delete_pool(self, pool_name: str) -> None:
        self.pools.pop(pool_name, None)

    async def remove_voice_from_all(self, voice_id: str) -> None:
        for voice_ids in self.pools.values():
            if voice_id in voice_ids:
                voice_ids.remove(voice_id)


class FakeJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        # Every save, in order — lets tests assert nothing overwrote a record.
        self.save_history: list[Job] = []

    async def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    async def save(self, job: Job) -> None:
        snapshot = job.model_copy(deep=True)
        self.jobs[job.id] = snapshot
        self.save_history.append(snapshot)

    async def mark_active_jobs_failed(self, message: str) -> int:
        n = 0
        for job in self.jobs.values():
            if job.status in ("queued", "running"):
                job.status = "failed"
                job.message = message
                n += 1
        return n


class FakeMetadataRepository:
    def __init__(self) -> None:
        self.line_hashes: dict[str, tuple[list[str], str]] = {}

    async def save_line_hashes(
        self, story_id: str, line_hashes: list[str], language: str
    ) -> None:
        self.line_hashes[story_id] = (list(line_hashes), language)

    async def load_line_hashes(self, story_id: str) -> tuple[list[str], str] | None:
        return self.line_hashes.get(story_id)


class FakeRepos:
    def __init__(self) -> None:
        self.stories = FakeStoryRepository()
        self.voices = FakeVoiceRepository()
        self.pools = FakePoolRepository()
        self.jobs = FakeJobRepository()
        self.metadata = FakeMetadataRepository()


@pytest.fixture
def fake_repos():
    fakes = FakeRepos()
    repo_factory._db_story_repo = fakes.stories
    repo_factory._db_voice_repo = fakes.voices
    repo_factory._db_pool_repo = fakes.pools
    repo_factory._db_job_repo = fakes.jobs
    repo_factory._db_metadata_repo = fakes.metadata
    yield fakes
    repo_factory.reset_repositories()


@pytest.fixture
def clean_jobs_state():
    """Reset the in-memory job queue state around a test.

    The queue and lock are recreated (not drained): asyncio primitives bind to
    the first event loop that uses them, and pytest runs each test in a fresh
    loop.
    """
    import asyncio

    def _reset() -> None:
        jobs_service._active_jobs.clear()
        jobs_service._cancelled_ids.clear()
        jobs_service._job_queue = asyncio.Queue()
        jobs_service._enqueue_lock = asyncio.Lock()

    _reset()
    yield
    _reset()
