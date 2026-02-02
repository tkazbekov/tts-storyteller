"""Tests for resolution and incremental hashing."""

from lib.incremental import compute_line_hash
from lib.models import ResolvedLine, Role, StoryLine, StoryTemplate
from lib.resolution import resolve_story


def test_resolve_story_actor_id_overrides_casting():
    story = StoryTemplate(
        schemaVersion=1,
        title="Test Story",
        defaultVoiceId="narrator",
        roles=[Role(roleId=0, name="Narrator"), Role(roleId=1, name="Child")],
        casting={"1": "child_voice"},
        lines=[
            StoryLine(id=0, roleId=0, line="Hello"),
            StoryLine(id=1, roleId=1, line="Hi", actorId="override_voice"),
        ],
    )

    resolved = resolve_story(story, {"narrator", "child_voice", "override_voice"})
    assert resolved[0].voiceId == "narrator"
    assert resolved[1].voiceId == "override_voice"


def test_compute_line_hash_changes_with_language_and_voice():
    base_line = ResolvedLine(id=0, roleId=0, voiceId="voice_a", line="Hello")
    hash_en = compute_line_hash(base_line, "English")
    hash_es = compute_line_hash(base_line, "Spanish")

    changed_voice_line = ResolvedLine(id=0, roleId=0, voiceId="voice_b", line="Hello")
    hash_voice = compute_line_hash(changed_voice_line, "English")

    assert hash_en != hash_es
    assert hash_en != hash_voice
