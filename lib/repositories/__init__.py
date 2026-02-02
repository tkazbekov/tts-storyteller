"""Repository abstractions for data persistence."""

from lib.repositories.base import (
    JobRepository,
    MetadataRepository,
    PoolRepository,
    StoryRepository,
    VoiceRepository,
)
from lib.repositories.factory import (
    get_job_repository,
    get_metadata_repository,
    get_pool_repository,
    get_story_repository,
    get_voice_repository,
)

__all__ = [
    # Protocols
    "StoryRepository",
    "VoiceRepository",
    "PoolRepository",
    "JobRepository",
    "MetadataRepository",
    # Factories
    "get_story_repository",
    "get_voice_repository",
    "get_pool_repository",
    "get_job_repository",
    "get_metadata_repository",
]
