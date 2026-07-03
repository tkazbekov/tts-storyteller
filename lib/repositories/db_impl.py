"""Database-backed repository implementations using SQLAlchemy."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lib.database import get_session
from lib.db_models import (
    JobModel,
    StoryGenerationMetadataModel,
    StoryLineModel,
    StoryModel,
    StoryRoleModel,
    VoiceModel,
    VoicePoolMemberModel,
    VoicePoolModel,
)
from lib.models import Job, Role, StoryLine, StoryTemplate, VoiceConfig
from lib.paths import get_prompt_path, get_voice_ref_audio_path


class DbStoryRepository:
    """Postgres-backed story repository."""

    async def get(self, story_id: str) -> StoryTemplate:
        """Load a story by ID (UUID or slug)."""
        async with get_session() as session:
            # Try UUID first, then slug
            try:
                uuid_id = uuid.UUID(story_id)
                stmt = select(StoryModel).where(StoryModel.id == uuid_id)
            except ValueError:
                # It's a slug
                stmt = select(StoryModel).where(StoryModel.slug == story_id)

            result = await session.execute(stmt)
            story_model = result.scalar_one_or_none()

            if not story_model:
                raise KeyError(f"Story '{story_id}' not found")

            return await self._model_to_template(session, story_model)

    async def list_ids(self) -> list[str]:
        """List all story slugs."""
        async with get_session() as session:
            stmt = select(StoryModel.slug).order_by(StoryModel.slug)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save(self, story_id: str, story: StoryTemplate) -> None:
        """Save a story (create or update)."""
        async with get_session() as session:
            # Check if story exists by slug
            stmt = select(StoryModel).where(StoryModel.slug == story_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.title = story.title
                existing.language = story.language
                existing.default_voice_id = story.defaultVoiceId
                existing.casting = story.casting

                # Delete and recreate roles and lines
                await session.execute(
                    delete(StoryRoleModel).where(StoryRoleModel.story_id == existing.id)
                )
                await session.execute(
                    delete(StoryLineModel).where(StoryLineModel.story_id == existing.id)
                )

                story_uuid = existing.id
            else:
                # Create new: use story.id set by the route so response and DB agree
                story_uuid = story.id if story.id is not None else uuid.uuid4()
                story_model = StoryModel(
                    id=story_uuid,
                    slug=story_id,
                    title=story.title,
                    language=story.language,
                    default_voice_id=story.defaultVoiceId,
                    casting=story.casting,
                )
                session.add(story_model)

            # Add roles
            for role in story.roles:
                role_model = StoryRoleModel(
                    story_id=story_uuid,
                    role_id=role.roleId,
                    name=role.name,
                    notes=role.notes,
                )
                session.add(role_model)

            # Add lines
            for idx, line in enumerate(story.lines):
                line_model = StoryLineModel(
                    story_id=story_uuid,
                    line_index=idx,
                    role_id=line.roleId,
                    line_text=line.line,
                    extra=line.extra,
                    actor_id=line.actorId,
                )
                session.add(line_model)

    async def exists(self, story_id: str) -> bool:
        """Check if a story exists."""
        async with get_session() as session:
            # Try UUID first, then slug
            try:
                uuid_id = uuid.UUID(story_id)
                stmt = select(StoryModel.id).where(StoryModel.id == uuid_id)
            except ValueError:
                stmt = select(StoryModel.id).where(StoryModel.slug == story_id)

            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def delete(self, story_id: str) -> None:
        """Delete a story."""
        async with get_session() as session:
            # Try UUID first, then slug
            try:
                uuid_id = uuid.UUID(story_id)
                stmt = delete(StoryModel).where(StoryModel.id == uuid_id)
            except ValueError:
                stmt = delete(StoryModel).where(StoryModel.slug == story_id)

            await session.execute(stmt)

    async def _model_to_template(self, session: AsyncSession, model: StoryModel) -> StoryTemplate:
        """Convert a database model to a StoryTemplate."""
        # Load roles
        roles_stmt = (
            select(StoryRoleModel)
            .where(StoryRoleModel.story_id == model.id)
            .order_by(StoryRoleModel.role_id)
        )
        roles_result = await session.execute(roles_stmt)
        role_models = roles_result.scalars().all()

        roles = [Role(roleId=r.role_id, name=r.name, notes=r.notes) for r in role_models]

        # Load lines
        lines_stmt = (
            select(StoryLineModel)
            .where(StoryLineModel.story_id == model.id)
            .order_by(StoryLineModel.line_index)
        )
        lines_result = await session.execute(lines_stmt)
        line_models = lines_result.scalars().all()

        lines = [
            StoryLine(
                id=ln.line_index,
                roleId=ln.role_id,
                line=ln.line_text,
                extra=ln.extra,
                actorId=ln.actor_id,
            )
            for ln in line_models
        ]

        return StoryTemplate(
            id=model.id,
            slug=model.slug,
            schemaVersion=1,
            title=model.title,
            language=model.language,
            defaultVoiceId=model.default_voice_id,
            casting=model.casting,
            roles=roles,
            lines=lines,
        )


class DbVoiceRepository:
    """Postgres-backed voice repository."""

    async def get(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice configuration by ID."""
        async with get_session() as session:
            stmt = select(VoiceModel).where(VoiceModel.id == voice_id)
            result = await session.execute(stmt)
            voice = result.scalar_one_or_none()

            if not voice:
                return None

            return {
                "id": voice.id,
                "language": voice.language,
                "instruction": voice.instruction,
                "sample_text": voice.sample_text,
                "backend": voice.backend,
            }

    async def get_info(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice info including paths."""
        voice = await self.get(voice_id)
        if not voice:
            return None

        backend = voice.get("backend", "qwen")
        prompt_path = get_prompt_path(voice_id, backend)
        ref_audio_path = get_voice_ref_audio_path(voice_id, backend)

        return {
            "id": voice_id,
            "language": voice.get("language", "English"),
            "instruction": voice.get("instruction", ""),
            "sample_text": voice.get("sample_text"),
            "backend": backend,
            "promptPath": str(prompt_path) if prompt_path.exists() else None,
            "refAudioPath": str(ref_audio_path) if ref_audio_path.exists() else None,
        }

    async def list_all(self) -> list[dict[str, Any]]:
        """List all voice configurations."""
        async with get_session() as session:
            stmt = select(VoiceModel).order_by(VoiceModel.id)
            result = await session.execute(stmt)
            voices = result.scalars().all()

            return [
                {
                    "id": v.id,
                    "language": v.language,
                    "instruction": v.instruction,
                    "sample_text": v.sample_text,
                    "backend": v.backend,
                }
                for v in voices
            ]

    async def save(self, voice_id: str, voice_config: VoiceConfig) -> None:
        """Save voice configuration."""
        async with get_session() as session:
            stmt = select(VoiceModel).where(VoiceModel.id == voice_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.language = voice_config.language
                existing.instruction = voice_config.instruction
                existing.sample_text = voice_config.sample_text
                existing.backend = voice_config.backend
            else:
                voice = VoiceModel(
                    id=voice_config.id,
                    language=voice_config.language,
                    instruction=voice_config.instruction,
                    sample_text=voice_config.sample_text,
                    backend=voice_config.backend,
                )
                session.add(voice)

    async def delete(self, voice_id: str) -> None:
        """Delete voice configuration."""
        async with get_session() as session:
            stmt = delete(VoiceModel).where(VoiceModel.id == voice_id)
            await session.execute(stmt)

    async def get_available_ids(self) -> set[str]:
        """Get set of voice IDs with backend-specific prompt files."""
        all_voices = await self.list_all()
        return {
            v["id"]
            for v in all_voices
            if get_prompt_path(v["id"], v.get("backend", "qwen")).exists()
        }

    async def has_prompt(self, voice_id: str) -> bool:
        """Check if voice has a backend-specific prompt file."""
        voice = await self.get(voice_id)
        return bool(voice and get_prompt_path(voice_id, voice.get("backend", "qwen")).exists())


class DbPoolRepository:
    """Postgres-backed pool repository."""

    async def get_voices(self, pool_name: str) -> list[str]:
        """Get voice IDs in a pool."""
        async with get_session() as session:
            stmt = (
                select(VoicePoolMemberModel.voice_id)
                .join(VoicePoolModel)
                .where(VoicePoolModel.name == pool_name)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_pools(self) -> set[str]:
        """List all pool names."""
        async with get_session() as session:
            stmt = select(VoicePoolModel.name)
            result = await session.execute(stmt)
            return set(result.scalars().all())

    async def get_all_pools(self) -> dict[str, list[str]]:
        """Get all pools with their voice IDs."""
        async with get_session() as session:
            # Single outer join so pools with no members still appear.
            stmt = (
                select(VoicePoolModel.name, VoicePoolMemberModel.voice_id)
                .outerjoin(
                    VoicePoolMemberModel,
                    VoicePoolMemberModel.pool_id == VoicePoolModel.id,
                )
                .order_by(VoicePoolModel.name)
            )
            result = await session.execute(stmt)

            pool_dict: dict[str, list[str]] = {}
            for pool_name, voice_id in result.all():
                members = pool_dict.setdefault(pool_name, [])
                if voice_id is not None:
                    members.append(voice_id)

            return pool_dict

    async def save_pool(self, pool_name: str, voice_ids: list[str]) -> None:
        """Save or update a pool."""
        async with get_session() as session:
            stmt = select(VoicePoolModel).where(VoicePoolModel.name == pool_name)
            result = await session.execute(stmt)
            pool = result.scalar_one_or_none()

            if pool:
                # Clear existing members
                await session.execute(
                    delete(VoicePoolMemberModel).where(VoicePoolMemberModel.pool_id == pool.id)
                )
            else:
                # Create new pool
                pool = VoicePoolModel(name=pool_name)
                session.add(pool)
                await session.flush()  # Get the pool.id

            # Add members
            for voice_id in voice_ids:
                member = VoicePoolMemberModel(pool_id=pool.id, voice_id=voice_id)
                session.add(member)

    async def delete_pool(self, pool_name: str) -> None:
        """Delete a pool."""
        async with get_session() as session:
            stmt = delete(VoicePoolModel).where(VoicePoolModel.name == pool_name)
            await session.execute(stmt)

    async def remove_voice_from_all(self, voice_id: str) -> None:
        """Remove a voice from all pools."""
        async with get_session() as session:
            stmt = delete(VoicePoolMemberModel).where(VoicePoolMemberModel.voice_id == voice_id)
            await session.execute(stmt)


async def _resolve_story_id_to_uuid(session: AsyncSession, story_id: str) -> uuid.UUID | None:
    """Resolve story_id (UUID string or slug) to story UUID."""
    try:
        return uuid.UUID(story_id)
    except ValueError:
        stmt = select(StoryModel.id).where(StoryModel.slug == story_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


class DbJobRepository:
    """Postgres-backed job repository."""

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        async with get_session() as session:
            try:
                uuid_id = uuid.UUID(job_id)
            except ValueError:
                return None

            stmt = select(JobModel).where(JobModel.id == uuid_id)
            result = await session.execute(stmt)
            job_model = result.scalar_one_or_none()

            if not job_model:
                return None

            return self._model_to_job(job_model)

    async def save(self, job: Job) -> None:
        """Save a job."""
        async with get_session() as session:
            job_uuid = uuid.UUID(job.id)
            story_uuid = (
                await _resolve_story_id_to_uuid(session, job.storyId) if job.storyId else None
            )
            stmt = select(JobModel).where(JobModel.id == job_uuid)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.type = job.type
                existing.status = job.status
                existing.story_id = story_uuid
                existing.voice_id = job.voiceId
                existing.message = job.message
                existing.output_path = job.outputPath
                existing.request_params = job.requestParams
                existing.started_at = (
                    datetime.fromisoformat(job.startedAt) if job.startedAt else None
                )
                existing.finished_at = (
                    datetime.fromisoformat(job.finishedAt) if job.finishedAt else None
                )
            else:
                job_model = JobModel(
                    id=job_uuid,
                    type=job.type,
                    status=job.status,
                    story_id=story_uuid,
                    voice_id=job.voiceId,
                    message=job.message,
                    output_path=job.outputPath,
                    request_params=job.requestParams,
                    created_at=datetime.fromisoformat(job.createdAt),
                    started_at=(datetime.fromisoformat(job.startedAt) if job.startedAt else None),
                    finished_at=(
                        datetime.fromisoformat(job.finishedAt) if job.finishedAt else None
                    ),
                )
                session.add(job_model)

    async def mark_active_jobs_failed(self, message: str) -> int:
        """Mark all queued/running jobs as failed. Returns number updated."""
        async with get_session() as session:
            now = datetime.now(UTC)
            stmt = (
                update(JobModel)
                .where(JobModel.status.in_(["queued", "running"]))
                .values(status="failed", message=message, finished_at=now)
            )
            result = await session.execute(stmt)
            return getattr(result, "rowcount", 0) or 0

    def _model_to_job(self, model: JobModel) -> Job:
        """Convert a database model to a Job."""
        return Job(
            id=str(model.id),
            type=model.type,
            status=model.status,
            storyId=str(model.story_id) if model.story_id else None,
            voiceId=model.voice_id,
            message=model.message,
            outputPath=model.output_path,
            requestParams=model.request_params,
            createdAt=model.created_at.astimezone(UTC).isoformat(),
            startedAt=(model.started_at.astimezone(UTC).isoformat() if model.started_at else None),
            finishedAt=(
                model.finished_at.astimezone(UTC).isoformat() if model.finished_at else None
            ),
        )


class DbMetadataRepository:
    """Postgres-backed metadata repository."""

    async def save_line_hashes(self, story_id: str, line_hashes: list[str], language: str) -> None:
        """Save line hashes."""
        async with get_session() as session:
            story_uuid = await _resolve_story_id_to_uuid(session, story_id)
            if not story_uuid:
                return

            # Check if metadata exists
            stmt = select(StoryGenerationMetadataModel).where(
                StoryGenerationMetadataModel.story_id == story_uuid
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.line_hashes = line_hashes
                existing.language = language
            else:
                metadata = StoryGenerationMetadataModel(
                    story_id=story_uuid,
                    line_hashes=line_hashes,
                    language=language,
                )
                session.add(metadata)

    async def load_line_hashes(self, story_id: str) -> tuple[list[str], str] | None:
        """Load line hashes and language."""
        async with get_session() as session:
            story_uuid = await _resolve_story_id_to_uuid(session, story_id)
            if not story_uuid:
                return None

            stmt = select(StoryGenerationMetadataModel).where(
                StoryGenerationMetadataModel.story_id == story_uuid
            )
            result = await session.execute(stmt)
            metadata = result.scalar_one_or_none()

            if not metadata:
                return None

            return (metadata.line_hashes, metadata.language)
