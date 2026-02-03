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
        return await self._get_async(story_id)

    async def _get_async(self, story_id: str) -> StoryTemplate:
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

    async def get_by_slug(self, slug: str) -> StoryTemplate:
        """Load a story by slug."""
        return await self._get_by_slug_async(slug)

    async def _get_by_slug_async(self, slug: str) -> StoryTemplate:
        async with get_session() as session:
            stmt = select(StoryModel).where(StoryModel.slug == slug)
            result = await session.execute(stmt)
            story_model = result.scalar_one_or_none()

            if not story_model:
                raise KeyError(f"Story with slug '{slug}' not found")

            return await self._model_to_template(session, story_model)

    async def list_ids(self) -> list[str]:
        """List all story slugs."""
        return await self._list_ids_async()

    async def _list_ids_async(self) -> list[str]:
        async with get_session() as session:
            stmt = select(StoryModel.slug).order_by(StoryModel.slug)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save(self, story_id: str, story: StoryTemplate) -> None:
        """Save a story (create or update)."""
        await self._save_async(story_id, story)

    async def _save_async(self, story_id: str, story: StoryTemplate) -> None:
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
        return await self._exists_async(story_id)

    async def _exists_async(self, story_id: str) -> bool:
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
        await self._delete_async(story_id)

    async def _delete_async(self, story_id: str) -> None:
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
        return await self._get_async(voice_id)

    async def _get_async(self, voice_id: str) -> dict[str, Any] | None:
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
            }

    async def get_info(self, voice_id: str) -> dict[str, Any] | None:
        """Get voice info including paths."""
        voice = await self.get(voice_id)
        if not voice:
            return None

        prompt_path = get_prompt_path(voice_id)
        ref_audio_path = get_voice_ref_audio_path(voice_id)

        return {
            "id": voice_id,
            "language": voice.get("language", "English"),
            "instruction": voice.get("instruction", ""),
            "sample_text": voice.get("sample_text"),
            "promptPath": str(prompt_path) if prompt_path.exists() else None,
            "refAudioPath": str(ref_audio_path) if ref_audio_path.exists() else None,
        }

    async def list_all(self) -> list[dict[str, Any]]:
        """List all voice configurations."""
        return await self._list_all_async()

    async def _list_all_async(self) -> list[dict[str, Any]]:
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
                }
                for v in voices
            ]

    async def save(self, voice_id: str, voice_config: VoiceConfig) -> None:
        """Save voice configuration."""
        await self._save_async(voice_id, voice_config)

    async def _save_async(self, voice_id: str, voice_config: VoiceConfig) -> None:
        async with get_session() as session:
            stmt = select(VoiceModel).where(VoiceModel.id == voice_id)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.language = voice_config.language
                existing.instruction = voice_config.instruction
                existing.sample_text = voice_config.sample_text
            else:
                voice = VoiceModel(
                    id=voice_config.id,
                    language=voice_config.language,
                    instruction=voice_config.instruction,
                    sample_text=voice_config.sample_text,
                )
                session.add(voice)

    async def delete(self, voice_id: str) -> None:
        """Delete voice configuration."""
        await self._delete_async(voice_id)

    async def _delete_async(self, voice_id: str) -> None:
        async with get_session() as session:
            stmt = delete(VoiceModel).where(VoiceModel.id == voice_id)
            await session.execute(stmt)

    async def get_available_ids(self) -> set[str]:
        """Get set of voice IDs with prompt files."""
        all_voices = await self.list_all()
        return {v["id"] for v in all_voices if get_prompt_path(v["id"]).exists()}

    async def has_prompt(self, voice_id: str) -> bool:
        """Check if voice has a prompt file."""
        return get_prompt_path(voice_id).exists()


class DbPoolRepository:
    """Postgres-backed pool repository."""

    async def get_voices(self, pool_name: str) -> list[str]:
        """Get voice IDs in a pool."""
        return await self._get_voices_async(pool_name)

    async def _get_voices_async(self, pool_name: str) -> list[str]:
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
        return await self._list_pools_async()

    async def _list_pools_async(self) -> set[str]:
        async with get_session() as session:
            stmt = select(VoicePoolModel.name)
            result = await session.execute(stmt)
            return set(result.scalars().all())

    async def get_all_pools(self) -> dict[str, list[str]]:
        """Get all pools with their voice IDs."""
        return await self._get_all_pools_async()

    async def _get_all_pools_async(self) -> dict[str, list[str]]:
        async with get_session() as session:
            stmt = select(VoicePoolModel)
            result = await session.execute(stmt)
            pools = result.scalars().all()

            pool_dict: dict[str, list[str]] = {}
            for pool in pools:
                members_stmt = select(VoicePoolMemberModel.voice_id).where(
                    VoicePoolMemberModel.pool_id == pool.id
                )
                members_result = await session.execute(members_stmt)
                pool_dict[pool.name] = list(members_result.scalars().all())

            return pool_dict

    async def save_pool(self, pool_name: str, voice_ids: list[str]) -> None:
        """Save or update a pool."""
        await self._save_pool_async(pool_name, voice_ids)

    async def _save_pool_async(self, pool_name: str, voice_ids: list[str]) -> None:
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
        await self._delete_pool_async(pool_name)

    async def _delete_pool_async(self, pool_name: str) -> None:
        async with get_session() as session:
            stmt = delete(VoicePoolModel).where(VoicePoolModel.name == pool_name)
            await session.execute(stmt)

    async def add_voice(self, voice_id: str, pool_name: str) -> None:
        """Add a voice to a pool."""
        await self._add_voice_async(voice_id, pool_name)

    async def _add_voice_async(self, voice_id: str, pool_name: str) -> None:
        async with get_session() as session:
            # Get or create pool
            stmt = select(VoicePoolModel).where(VoicePoolModel.name == pool_name)
            result = await session.execute(stmt)
            pool = result.scalar_one_or_none()

            if not pool:
                pool = VoicePoolModel(name=pool_name)
                session.add(pool)
                await session.flush()

            # Check if member exists
            member_stmt = select(VoicePoolMemberModel).where(
                VoicePoolMemberModel.pool_id == pool.id,
                VoicePoolMemberModel.voice_id == voice_id,
            )
            member_result = await session.execute(member_stmt)
            if not member_result.scalar_one_or_none():
                member = VoicePoolMemberModel(pool_id=pool.id, voice_id=voice_id)
                session.add(member)

    async def remove_voice(self, voice_id: str, pool_name: str) -> None:
        """Remove a voice from a pool."""
        await self._remove_voice_async(voice_id, pool_name)

    async def _remove_voice_async(self, voice_id: str, pool_name: str) -> None:
        async with get_session() as session:
            stmt = delete(VoicePoolMemberModel).where(
                VoicePoolMemberModel.voice_id == voice_id,
                VoicePoolMemberModel.pool_id.in_(
                    select(VoicePoolModel.id).where(VoicePoolModel.name == pool_name)
                ),
            )
            await session.execute(stmt)

    async def remove_voice_from_all(self, voice_id: str) -> None:
        """Remove a voice from all pools."""
        await self._remove_voice_from_all_async(voice_id)

    async def _remove_voice_from_all_async(self, voice_id: str) -> None:
        async with get_session() as session:
            stmt = delete(VoicePoolMemberModel).where(VoicePoolMemberModel.voice_id == voice_id)
            await session.execute(stmt)


class DbJobRepository:
    """Postgres-backed job repository."""

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return await self._get_async(job_id)

    async def _get_async(self, job_id: str) -> Job | None:
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
        await self._save_async(job)

    async def _save_async(self, job: Job) -> None:
        async with get_session() as session:
            job_uuid = uuid.UUID(job.id)
            stmt = select(JobModel).where(JobModel.id == job_uuid)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.type = job.type
                existing.status = job.status
                existing.story_id = uuid.UUID(job.storyId) if job.storyId else None
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
                    story_id=uuid.UUID(job.storyId) if job.storyId else None,
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

    async def get_active_for_story(self, story_id: str) -> Job | None:
        """Get active job for a story."""
        return await self._get_active_for_story_async(story_id)

    async def _get_active_for_story_async(self, story_id: str) -> Job | None:
        async with get_session() as session:
            # story_id might be a UUID or a slug; for jobs we store UUID
            # For now, assume it could be passed as slug and we need to look up
            story_uuid: uuid.UUID | None
            try:
                story_uuid = uuid.UUID(story_id)
            except ValueError:
                # Look up story by slug
                story_stmt = select(StoryModel.id).where(StoryModel.slug == story_id)
                story_result = await session.execute(story_stmt)
                story_uuid = story_result.scalar_one_or_none()
                if not story_uuid:
                    return None

            stmt = (
                select(JobModel)
                .where(
                    JobModel.story_id == story_uuid,
                    JobModel.status.in_(["queued", "running"]),
                )
                .order_by(JobModel.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            job_model = result.scalar_one_or_none()

            return self._model_to_job(job_model) if job_model else None

    async def get_active_for_voice(self, voice_id: str) -> Job | None:
        """Get active job for a voice."""
        return await self._get_active_for_voice_async(voice_id)

    async def _get_active_for_voice_async(self, voice_id: str) -> Job | None:
        async with get_session() as session:
            stmt = (
                select(JobModel)
                .where(
                    JobModel.voice_id == voice_id,
                    JobModel.status.in_(["queued", "running"]),
                )
                .order_by(JobModel.created_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            job_model = result.scalar_one_or_none()

            return self._model_to_job(job_model) if job_model else None

    async def get_queued_jobs(self) -> list[Job]:
        """Get all queued jobs."""
        return await self._get_queued_jobs_async()

    async def _get_queued_jobs_async(self) -> list[Job]:
        async with get_session() as session:
            stmt = select(JobModel).where(JobModel.status == "queued").order_by(JobModel.created_at)
            result = await session.execute(stmt)
            job_models = result.scalars().all()

            return [self._model_to_job(j) for j in job_models]

    async def mark_active_jobs_failed(self, message: str) -> int:
        """Mark all queued/running jobs as failed. Returns number updated."""
        return await self._mark_active_jobs_failed_async(message)

    async def _mark_active_jobs_failed_async(self, message: str) -> int:
        async with get_session() as session:
            now = datetime.now(UTC)
            stmt = (
                update(JobModel)
                .where(JobModel.status.in_(["queued", "running"]))
                .values(status="failed", message=message, finished_at=now)
            )
            result = await session.execute(stmt)
            return result.rowcount or 0

    async def update_status(
        self,
        job_id: str,
        status: str,
        message: str | None = None,
        output_path: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        """Update job status."""
        await self._update_status_async(
            job_id, status, message, output_path, started_at, finished_at
        )

    async def _update_status_async(
        self,
        job_id: str,
        status: str,
        message: str | None = None,
        output_path: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        async with get_session() as session:
            try:
                job_uuid = uuid.UUID(job_id)
            except ValueError:
                return

            stmt = select(JobModel).where(JobModel.id == job_uuid)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()

            if not job:
                return

            job.status = status
            if message is not None:
                job.message = message
            if output_path is not None:
                job.output_path = output_path
            if started_at is not None:
                job.started_at = datetime.fromisoformat(started_at)
            if finished_at is not None:
                job.finished_at = datetime.fromisoformat(finished_at)

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
        await self._save_line_hashes_async(story_id, line_hashes, language)

    async def _save_line_hashes_async(
        self, story_id: str, line_hashes: list[str], language: str
    ) -> None:
        async with get_session() as session:
            # Get story UUID
            story_uuid: uuid.UUID | None
            try:
                story_uuid = uuid.UUID(story_id)
            except ValueError:
                # Look up by slug
                story_stmt = select(StoryModel.id).where(StoryModel.slug == story_id)
                story_result = await session.execute(story_stmt)
                story_uuid = story_result.scalar_one_or_none()
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
        return await self._load_line_hashes_async(story_id)

    async def _load_line_hashes_async(self, story_id: str) -> tuple[list[str], str] | None:
        async with get_session() as session:
            # Get story UUID
            story_uuid: uuid.UUID | None
            try:
                story_uuid = uuid.UUID(story_id)
            except ValueError:
                # Look up by slug
                story_stmt = select(StoryModel.id).where(StoryModel.slug == story_id)
                story_result = await session.execute(story_stmt)
                story_uuid = story_result.scalar_one_or_none()
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
