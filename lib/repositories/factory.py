"""Repository factory functions that provide database-backed implementations."""

from __future__ import annotations

import threading

from lib.repositories.base import (
    JobRepository,
    MetadataRepository,
    PoolRepository,
    StoryRepository,
    VoiceRepository,
)
from lib.repositories.db_impl import (
    DbJobRepository,
    DbMetadataRepository,
    DbPoolRepository,
    DbStoryRepository,
    DbVoiceRepository,
)

# Lock for thread-safe singleton initialization
_lock = threading.Lock()

# Singleton instances for database repositories
_db_story_repo: DbStoryRepository | None = None
_db_voice_repo: DbVoiceRepository | None = None
_db_pool_repo: DbPoolRepository | None = None
_db_job_repo: DbJobRepository | None = None
_db_metadata_repo: DbMetadataRepository | None = None


def get_story_repository() -> StoryRepository:
    """Get the story repository (database-backed)."""
    global _db_story_repo

    if _db_story_repo is None:
        with _lock:
            if _db_story_repo is None:
                _db_story_repo = DbStoryRepository()
    return _db_story_repo


def get_voice_repository() -> VoiceRepository:
    """Get the voice repository (database-backed)."""
    global _db_voice_repo

    if _db_voice_repo is None:
        with _lock:
            if _db_voice_repo is None:
                _db_voice_repo = DbVoiceRepository()
    return _db_voice_repo


def get_pool_repository() -> PoolRepository:
    """Get the pool repository (database-backed)."""
    global _db_pool_repo

    if _db_pool_repo is None:
        with _lock:
            if _db_pool_repo is None:
                _db_pool_repo = DbPoolRepository()
    return _db_pool_repo


def get_job_repository() -> JobRepository:
    """Get the job repository (database-backed)."""
    global _db_job_repo

    if _db_job_repo is None:
        with _lock:
            if _db_job_repo is None:
                _db_job_repo = DbJobRepository()
    return _db_job_repo


def get_metadata_repository() -> MetadataRepository:
    """Get the metadata repository (database-backed)."""
    global _db_metadata_repo

    if _db_metadata_repo is None:
        with _lock:
            if _db_metadata_repo is None:
                _db_metadata_repo = DbMetadataRepository()
    return _db_metadata_repo


def reset_repositories() -> None:
    """
    Reset all repository singletons (for testing).

    This clears all cached repository instances, allowing fresh
    instances to be created on next access.
    """
    global _db_story_repo, _db_voice_repo, _db_pool_repo, _db_job_repo
    global _db_metadata_repo

    with _lock:
        _db_story_repo = None
        _db_voice_repo = None
        _db_pool_repo = None
        _db_job_repo = None
        _db_metadata_repo = None
