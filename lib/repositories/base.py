"""Protocol definitions for repository interfaces."""

from __future__ import annotations

from typing import Any, Protocol

from lib.models import Job, StoryTemplate, VoiceConfig


class StoryRepository(Protocol):
    """Protocol for story persistence operations."""

    async def get(self, story_id: str) -> StoryTemplate:
        """
        Load a story by ID.

        Raises:
            KeyError: If story not found
        """
        ...

    async def list_ids(self) -> list[str]:
        """List all story IDs (slugs for file storage, UUIDs for DB)."""
        ...

    async def save(self, story_id: str, story: StoryTemplate) -> None:
        """Save a story (create or update)."""
        ...

    async def exists(self, story_id: str) -> bool:
        """Check if a story exists."""
        ...

    async def delete(self, story_id: str) -> None:
        """Delete a story."""
        ...


class VoiceRepository(Protocol):
    """Protocol for voice persistence operations."""

    async def get(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice configuration by ID. Returns None if not found."""
        ...

    async def get_info(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice info including paths. Returns None if not found."""
        ...

    async def list_all(self) -> list[dict[str, Any]]:
        """List all voice configurations."""
        ...

    async def save(self, voice_id: str, voice_config: VoiceConfig) -> None:
        """Save voice configuration (create or update)."""
        ...

    async def delete(self, voice_id: str) -> None:
        """Delete a voice configuration."""
        ...

    async def get_available_ids(self) -> set[str]:
        """Get set of voice IDs that have prompt files."""
        ...

    async def has_prompt(self, voice_id: str) -> bool:
        """Check if a voice has a prompt file."""
        ...


class PoolRepository(Protocol):
    """Protocol for voice pool persistence operations."""

    async def get_voices(self, pool_name: str) -> list[str]:
        """Get voice IDs in a pool. Returns empty list if pool doesn't exist."""
        ...

    async def list_pools(self) -> set[str]:
        """List all pool names."""
        ...

    async def get_all_pools(self) -> dict[str, list[str]]:
        """Get all pools with their voice IDs."""
        ...

    async def save_pool(self, pool_name: str, voice_ids: list[str]) -> None:
        """Save or update a pool."""
        ...

    async def delete_pool(self, pool_name: str) -> None:
        """Delete a pool."""
        ...

    async def remove_voice_from_all(self, voice_id: str) -> None:
        """Remove a voice from all pools."""
        ...


class JobRepository(Protocol):
    """Protocol for job persistence operations."""

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID. Returns None if not found."""
        ...

    async def save(self, job: Job) -> None:
        """Save a job (create or update)."""
        ...

    async def mark_active_jobs_failed(self, message: str) -> int:
        """Mark all jobs with status queued/running as failed. Returns count. Used on startup only."""
        ...


class MetadataRepository(Protocol):
    """Protocol for generation metadata persistence."""

    async def save_line_hashes(self, story_id: str, line_hashes: list[str], language: str) -> None:
        """Save line hashes for incremental generation."""
        ...

    async def load_line_hashes(self, story_id: str) -> tuple[list[str], str] | None:
        """
        Load line hashes and language.

        Returns:
            Tuple of (line_hashes, language) or None if not found
        """
        ...
