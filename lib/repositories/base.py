"""Protocol definitions for repository interfaces."""

from __future__ import annotations

from typing import Any, Protocol

from lib.models import Job, StoryTemplate, VoiceConfig


class StoryRepository(Protocol):
    """Protocol for story persistence operations."""

    def get(self, story_id: str) -> StoryTemplate:
        """
        Load a story by ID.

        Raises:
            KeyError: If story not found
        """
        ...

    def get_by_slug(self, slug: str) -> StoryTemplate:
        """
        Load a story by slug.

        Raises:
            KeyError: If story not found
        """
        ...

    def list_ids(self) -> list[str]:
        """List all story IDs (slugs for file storage, UUIDs for DB)."""
        ...

    def save(self, story_id: str, story: StoryTemplate) -> None:
        """Save a story (create or update)."""
        ...

    def exists(self, story_id: str) -> bool:
        """Check if a story exists."""
        ...

    def delete(self, story_id: str) -> None:
        """Delete a story."""
        ...


class VoiceRepository(Protocol):
    """Protocol for voice persistence operations."""

    def get(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice configuration by ID. Returns None if not found."""
        ...

    def get_info(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice info including paths. Returns None if not found."""
        ...

    def list_all(self) -> list[dict[str, Any]]:
        """List all voice configurations."""
        ...

    def save(self, voice_id: str, voice_config: VoiceConfig) -> None:
        """Save voice configuration (create or update)."""
        ...

    def delete(self, voice_id: str) -> None:
        """Delete a voice configuration."""
        ...

    def get_available_ids(self) -> set[str]:
        """Get set of voice IDs that have prompt files."""
        ...

    def has_prompt(self, voice_id: str) -> bool:
        """Check if a voice has a prompt file."""
        ...


class PoolRepository(Protocol):
    """Protocol for voice pool persistence operations."""

    def get_voices(self, pool_name: str) -> list[str]:
        """Get voice IDs in a pool. Returns empty list if pool doesn't exist."""
        ...

    def list_pools(self) -> set[str]:
        """List all pool names."""
        ...

    def get_all_pools(self) -> dict[str, list[str]]:
        """Get all pools with their voice IDs."""
        ...

    def save_pool(self, pool_name: str, voice_ids: list[str]) -> None:
        """Save or update a pool."""
        ...

    def delete_pool(self, pool_name: str) -> None:
        """Delete a pool."""
        ...

    def add_voice(self, voice_id: str, pool_name: str) -> None:
        """Add a voice to a pool."""
        ...

    def remove_voice(self, voice_id: str, pool_name: str) -> None:
        """Remove a voice from a pool."""
        ...

    def remove_voice_from_all(self, voice_id: str) -> None:
        """Remove a voice from all pools."""
        ...


class JobRepository(Protocol):
    """Protocol for job persistence operations."""

    def get(self, job_id: str) -> Job | None:
        """Get a job by ID. Returns None if not found."""
        ...

    def save(self, job: Job) -> None:
        """Save a job (create or update)."""
        ...

    def get_active_for_story(self, story_id: str) -> Job | None:
        """Get active (queued/running) job for a story."""
        ...

    def get_active_for_voice(self, voice_id: str) -> Job | None:
        """Get active (queued/running) job for a voice."""
        ...

    def get_queued_jobs(self) -> list[Job]:
        """Get all queued jobs (for recovery on startup)."""
        ...

    def update_status(
        self,
        job_id: str,
        status: str,
        message: str | None = None,
        output_path: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        """Update job status and related fields."""
        ...


class MetadataRepository(Protocol):
    """Protocol for generation metadata persistence."""

    def save_line_hashes(self, story_id: str, line_hashes: list[str], language: str) -> None:
        """Save line hashes for incremental generation."""
        ...

    def load_line_hashes(self, story_id: str) -> tuple[list[str], str] | None:
        """
        Load line hashes and language.

        Returns:
            Tuple of (line_hashes, language) or None if not found
        """
        ...
