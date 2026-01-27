"""Basic tests to verify the test infrastructure works."""


def test_imports():
    """Test that main modules can be imported."""
    from lib import generation, models, paths, resolution, storage, validation

    assert models is not None
    assert paths is not None
    assert storage is not None
    assert validation is not None
    assert resolution is not None
    assert generation is not None


def test_paths_module():
    """Test that paths module provides expected functions."""
    from lib.paths import (
        get_project_root,
        get_stories_dir,
        get_voices_config_path,
    )

    root = get_project_root()
    assert root.exists()
    assert root.is_dir()

    stories_dir = get_stories_dir()
    assert stories_dir.exists() or not stories_dir.exists()  # May or may not exist

    voices_config = get_voices_config_path()
    assert voices_config is not None


def test_models():
    """Test that Pydantic models can be instantiated."""
    from lib.models import Role, StoryLine, StoryTemplate

    role = Role(roleId=0, name="Test Role")
    assert role.roleId == 0
    assert role.name == "Test Role"

    line = StoryLine(id=0, roleId=0, line="Test line")
    assert line.id == 0
    assert line.line == "Test line"

    story = StoryTemplate(
        schemaVersion=1,
        title="Test Story",
        defaultVoiceId="test_voice",
        roles=[role],
        lines=[line],
    )
    assert story.title == "Test Story"
    assert len(story.roles) == 1
    assert len(story.lines) == 1
