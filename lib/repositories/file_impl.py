"""File-based repository implementations wrapping existing storage functions."""

from __future__ import annotations

from typing import Any

from lib import storage
from lib.metadata import load_line_hashes as metadata_load_line_hashes
from lib.metadata import save_line_hashes as metadata_save_line_hashes
from lib.models import Job, ResolvedLine, StoryTemplate, VoiceConfig
from lib.paths import get_prompt_path, get_story_path


class FileStoryRepository:
    """File-based story repository using lib/storage.py."""

    def get(self, story_id: str) -> StoryTemplate:
        """Load a story by ID."""
        try:
            return storage.load_story(story_id)
        except FileNotFoundError as e:
            raise KeyError(str(e)) from e

    def get_by_slug(self, slug: str) -> StoryTemplate:
        """Load a story by slug (same as ID for file storage)."""
        return self.get(slug)

    def list_ids(self) -> list[str]:
        """List all story IDs."""
        return storage.list_stories()

    def save(self, story_id: str, story: StoryTemplate) -> None:
        """Save a story."""
        storage.save_story(story_id, story)

    def exists(self, story_id: str) -> bool:
        """Check if a story exists."""
        return get_story_path(story_id).exists()

    def delete(self, story_id: str) -> None:
        """Delete a story."""
        path = get_story_path(story_id)
        if path.exists():
            path.unlink()


class FileVoiceRepository:
    """File-based voice repository using lib/storage.py."""

    def get(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice configuration by ID."""
        return storage.load_voice_config(voice_id)

    def get_info(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice info including paths."""
        return storage.get_voice_info(voice_id)

    def list_all(self) -> list[dict[str, Any]]:
        """List all voice configurations."""
        return storage.load_voices_config()

    def save(self, voice_id: str, voice_config: VoiceConfig) -> None:
        """Save voice configuration."""
        storage.save_voice_config(voice_id, voice_config)

    def delete(self, voice_id: str) -> None:
        """Delete voice configuration."""
        storage.delete_voice_config(voice_id)

    def get_available_ids(self) -> set[str]:
        """Get set of voice IDs with prompt files."""
        return storage.get_available_voice_ids()

    def has_prompt(self, voice_id: str) -> bool:
        """Check if voice has a prompt file."""
        return get_prompt_path(voice_id).exists()


class FilePoolRepository:
    """File-based pool repository using lib/storage.py."""

    def get_voices(self, pool_name: str) -> list[str]:
        """Get voice IDs in a pool."""
        return storage.get_voices_by_pool(pool_name)

    def list_pools(self) -> set[str]:
        """List all pool names."""
        return storage.get_all_pools()

    def get_all_pools(self) -> dict[str, list[str]]:
        """Get all pools with their voice IDs."""
        return storage.load_pools_config()

    def save_pool(self, pool_name: str, voice_ids: list[str]) -> None:
        """Save or update a pool."""
        pools = storage.load_pools_config()
        pools[pool_name] = voice_ids
        storage.save_pools_config(pools)

    def delete_pool(self, pool_name: str) -> None:
        """Delete a pool."""
        pools = storage.load_pools_config()
        if pool_name in pools:
            del pools[pool_name]
            storage.save_pools_config(pools)

    def add_voice(self, voice_id: str, pool_name: str) -> None:
        """Add a voice to a pool."""
        storage.add_voice_to_pool(voice_id, pool_name)

    def remove_voice(self, voice_id: str, pool_name: str) -> None:
        """Remove a voice from a pool."""
        storage.remove_voice_from_pool(voice_id, pool_name)

    def remove_voice_from_all(self, voice_id: str) -> None:
        """Remove a voice from all pools."""
        storage.remove_voice_from_all_pools(voice_id)


class InMemoryJobRepository:
    """
    In-memory job repository.

    This maintains the current behavior where jobs are stored in memory
    and lost on server restart. The DB implementation will persist jobs.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._story_active_jobs: dict[str, str] = {}
        self._voice_active_jobs: dict[str, str] = {}

    def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def save(self, job: Job) -> None:
        """Save a job."""
        self._jobs[job.id] = job

        # Track active jobs by story/voice
        if job.status in ("queued", "running"):
            if job.storyId:
                self._story_active_jobs[job.storyId] = job.id
            if job.voiceId:
                self._voice_active_jobs[job.voiceId] = job.id
        else:
            # Job is no longer active, remove from tracking
            if job.storyId and self._story_active_jobs.get(job.storyId) == job.id:
                del self._story_active_jobs[job.storyId]
            if job.voiceId and self._voice_active_jobs.get(job.voiceId) == job.id:
                del self._voice_active_jobs[job.voiceId]

    def get_active_for_story(self, story_id: str) -> Job | None:
        """Get active job for a story."""
        job_id = self._story_active_jobs.get(story_id)
        if not job_id:
            return None
        job = self._jobs.get(job_id)
        if job and job.status in ("queued", "running"):
            return job
        return None

    def get_active_for_voice(self, voice_id: str) -> Job | None:
        """Get active job for a voice."""
        job_id = self._voice_active_jobs.get(voice_id)
        if not job_id:
            return None
        job = self._jobs.get(job_id)
        if job and job.status in ("queued", "running"):
            return job
        return None

    def get_queued_jobs(self) -> list[Job]:
        """Get all queued jobs."""
        return [j for j in self._jobs.values() if j.status == "queued"]

    def update_status(
        self,
        job_id: str,
        status: str,
        message: str | None = None,
        output_path: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        """Update job status."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = status
        if message is not None:
            job.message = message
        if output_path is not None:
            job.outputPath = output_path
        if started_at is not None:
            job.startedAt = started_at
        if finished_at is not None:
            job.finishedAt = finished_at

        # Update tracking when job completes/fails
        if status not in ("queued", "running"):
            if job.storyId and self._story_active_jobs.get(job.storyId) == job.id:
                del self._story_active_jobs[job.storyId]
            if job.voiceId and self._voice_active_jobs.get(job.voiceId) == job.id:
                del self._voice_active_jobs[job.voiceId]


class FileMetadataRepository:
    """
    File-based metadata repository using lib/metadata.py.

    Note: This stores metadata in the output directory alongside audio files.
    The DB implementation will store in a dedicated table.
    """

    def save_line_hashes(self, story_id: str, line_hashes: list[str], language: str) -> None:
        """Save line hashes. Wraps lib/metadata directly with resolved lines."""
        # Create minimal ResolvedLine objects for the existing save function
        # We need to work with the existing API that computes hashes internally
        raise NotImplementedError(
            "Use lib/metadata.save_line_hashes directly with ResolvedLine objects"
        )

    def save_line_hashes_from_resolved(
        self, story_id: str, resolved_lines: list[ResolvedLine], language: str
    ) -> None:
        """Save line hashes from resolved lines (uses existing metadata API)."""
        metadata_save_line_hashes(story_id, resolved_lines, language)

    def load_line_hashes(self, story_id: str) -> tuple[list[str], str] | None:
        """Load line hashes and language."""
        return metadata_load_line_hashes(story_id)
