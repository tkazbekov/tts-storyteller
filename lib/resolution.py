"""Role-to-voice resolution logic for story templates."""

from lib.models import ResolvedLine, StoryTemplate


def resolve_story(story: StoryTemplate, available_voices: set[str]) -> list[ResolvedLine]:
    """
    Resolve roles to voices for a story template.

    Resolution order: line.actorId -> casting[roleId] -> defaultVoiceId

    Args:
        story: The story template to resolve
        available_voices: Set of available voice IDs (must include defaultVoiceId)

    Returns:
        List of resolved lines with voice assignments

    Raises:
        ValueError: If a resolved voice ID is not in available_voices
    """
    if story.defaultVoiceId not in available_voices:
        raise ValueError(f"defaultVoiceId '{story.defaultVoiceId}' not found in available voices")

    casting = story.casting or {}
    resolved: list[ResolvedLine] = []

    for line in story.lines:
        # Resolution order: actorId -> casting -> defaultVoiceId
        voice_id = None
        if line.actorId:
            voice_id = line.actorId
        elif str(line.roleId) in casting:
            voice_id = casting[str(line.roleId)]
        else:
            voice_id = story.defaultVoiceId

        # Validate voice exists
        if voice_id not in available_voices:
            raise ValueError(
                f"Voice '{voice_id}' (resolved for line {line.id}, role {line.roleId}) "
                f"not found in available voices"
            )

        resolved.append(
            ResolvedLine(
                id=line.id,
                roleId=line.roleId,
                voiceId=voice_id,
                line=line.line,
                extra=line.extra,
            )
        )

    return resolved
