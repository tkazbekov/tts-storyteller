"""SQLAlchemy ORM models for the database schema."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[str]: JSONB,
    }


class StoryModel(Base):
    """Story database model."""

    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="English")
    default_voice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    casting: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    roles: Mapped[list[StoryRoleModel]] = relationship(
        "StoryRoleModel", back_populates="story", cascade="all, delete-orphan"
    )
    lines: Mapped[list[StoryLineModel]] = relationship(
        "StoryLineModel", back_populates="story", cascade="all, delete-orphan"
    )
    generation_metadata: Mapped[StoryGenerationMetadataModel | None] = relationship(
        "StoryGenerationMetadataModel",
        back_populates="story",
        uselist=False,
        cascade="all, delete-orphan",
    )


class StoryRoleModel(Base):
    """Story role database model."""

    __tablename__ = "story_roles"

    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    story: Mapped[StoryModel] = relationship("StoryModel", back_populates="roles")


class StoryLineModel(Base):
    """Story line database model."""

    __tablename__ = "story_lines"

    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    line_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, nullable=False)
    line_text: Mapped[str] = mapped_column(Text, nullable=False)
    extra: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationship
    story: Mapped[StoryModel] = relationship("StoryModel", back_populates="lines")


class VoiceModel(Base):
    """Voice database model."""

    __tablename__ = "voices"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    sample_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    backend: Mapped[str] = mapped_column(String(50), nullable=False, server_default="qwen")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    pool_memberships: Mapped[list[VoicePoolMemberModel]] = relationship(
        "VoicePoolMemberModel", back_populates="voice", cascade="all, delete-orphan"
    )


class VoicePoolModel(Base):
    """Voice pool database model."""

    __tablename__ = "voice_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationship
    members: Mapped[list[VoicePoolMemberModel]] = relationship(
        "VoicePoolMemberModel", back_populates="pool", cascade="all, delete-orphan"
    )


class VoicePoolMemberModel(Base):
    """Voice pool member database model."""

    __tablename__ = "voice_pool_members"

    pool_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("voice_pools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    voice_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("voices.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    pool: Mapped[VoicePoolModel] = relationship("VoicePoolModel", back_populates="members")
    voice: Mapped[VoiceModel] = relationship("VoiceModel", back_populates="pool_memberships")


class JobModel(Base):
    """Job database model."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    voice_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StoryGenerationMetadataModel(Base):
    """Story generation metadata database model for incremental generation."""

    __tablename__ = "story_generation_metadata"

    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    line_hashes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    story: Mapped[StoryModel] = relationship("StoryModel", back_populates="generation_metadata")
