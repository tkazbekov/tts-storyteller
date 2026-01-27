"""Pydantic models for API data structures."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Role(BaseModel):
    """A role in a story."""

    roleId: int = Field(..., ge=0, description="Unique role identifier")
    name: str = Field(..., min_length=1, description="Role name")
    notes: str | None = Field(None, description="Optional author notes")


class StoryLine(BaseModel):
    """A single line in a story."""

    id: int = Field(..., ge=0, description="Unique line identifier")
    roleId: int = Field(..., ge=0, description="Role that speaks this line")
    line: str = Field(..., min_length=1, description="The text to speak")
    extra: str | None = Field(None, description="Performance hint (e.g., 'curious, excited')")
    actorId: str | None = Field(
        None,
        min_length=1,
        description="Optional per-line voice override. Highest priority in voice resolution: actorId → casting[roleId] → defaultVoiceId",
    )


class StoryTemplate(BaseModel):
    """
    A story template with roles and lines.

    Voice assignment resolution order (for each line):
    1. line.actorId (if present) - per-line override
    2. casting[str(roleId)] (if present) - role-level assignment
    3. defaultVoiceId - fallback for all unassigned roles

    Example casting: {"0": "narrator_male", "1": "woman"} maps roleId 0 to narrator_male, roleId 1 to woman.
    """

    schemaVersion: Literal[1] = Field(1, description="Schema version")
    title: str = Field(..., min_length=1, description="Story title")
    defaultVoiceId: str = Field(
        ...,
        min_length=1,
        description="Fallback voice ID used when a role has no casting assignment and line has no actorId",
    )
    roles: list[Role] = Field(..., description="Story roles")
    casting: dict[str, str] | None = Field(
        None,
        description="Optional map of roleId (as string key) to voiceId (string value). "
        "Example: {'0': 'narrator_male', '1': 'woman'}. "
        "Keys must be string representations of roleId integers.",
        json_schema_extra={
            "example": {"0": "narrator_male", "1": "woman", "2": "child"}
        },
    )
    lines: list[StoryLine] = Field(..., description="Story lines")

    @field_validator("roles", "lines")
    @classmethod
    def validate_non_empty(cls, v: list) -> list:
        """Ensure roles and lines are non-empty."""
        if not v:
            raise ValueError("must not be empty")
        return v


class ResolvedLine(BaseModel):
    """
    A story line with resolved voice assignment.

    This is the result of resolving a StoryLine using the resolution order:
    actorId → casting[roleId] → defaultVoiceId
    """

    id: int = Field(..., ge=0, description="Line identifier")
    roleId: int = Field(..., ge=0, description="Role identifier")
    voiceId: str = Field(..., min_length=1, description="Resolved voice ID that will be used for this line")
    line: str = Field(..., min_length=1, description="The text to speak")
    extra: str | None = Field(None, description="Performance hint")


class Voice(BaseModel):
    """A voice definition."""

    id: str = Field(..., min_length=1)
    promptPath: str | None = Field(None, description="Path to prompt file")
    refAudioPath: str | None = Field(None, description="Path to reference audio")


class GenerateRequest(BaseModel):
    """Request body for story generation."""

    concat: bool = Field(False, description="Whether to concatenate outputs")
    concatOut: str | None = Field(None, description="Output path for concatenated audio")


class Job(BaseModel):
    """A generation job."""

    id: str = Field(..., description="Job identifier")
    type: str = Field(..., description="Job type (e.g., 'generate')")
    status: str = Field(..., description="Job status: queued, running, succeeded, failed")
    storyId: str | None = Field(None, description="Associated story ID")
    message: str | None = Field(None, description="Status message or error")
    outputPath: str | None = Field(None, description="Path to generated audio file")
    requestParams: dict[str, Any] | None = Field(
        None, description="Request parameters for generation"
    )
