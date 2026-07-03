"""Regression tests for story-global file indices in generate_story_audio.

Multi-backend stories are generated as per-backend subsets of the line list;
filenames and regeneration bookkeeping must use the story-global index or the
subsets collide/misname their outputs.
"""

from __future__ import annotations

import numpy as np
import pytest

import lib.paths as paths
from lib.backends.base import AudioResult, VoicePrompt
from lib.generation import generate_story_audio
from lib.models import ResolvedLine


class FakeBackend:
    """Minimal TTSBackend stand-in for generation tests."""

    def __init__(self, name: str = "qwen") -> None:
        self._name = name
        self.generated: list[str] = []  # texts actually synthesized

    @property
    def backend_name(self) -> str:
        return self._name

    def load_prompt(self, path) -> VoicePrompt:
        return VoicePrompt(backend=self._name, voice_id="", data={})

    def generate_voice_clone(self, text, language, voice_prompt) -> AudioResult:
        self.generated.append(text)
        return AudioResult(audio=np.zeros(16, dtype=np.float32), sample_rate=24000)


def _line(line_id: int, voice: str, text: str) -> ResolvedLine:
    return ResolvedLine(id=line_id, roleId=0, voiceId=voice, line=text)


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    """Point all path helpers at a temp project root with prompt files."""
    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path)
    for backend in ("qwen", "vibevoice"):
        prompts = tmp_path / "prompts" / backend
        prompts.mkdir(parents=True)
        for voice in ("alpha", "beta"):
            ext = ".pt" if backend == "qwen" else ".json"
            (prompts / f"{voice}{ext}").write_bytes(b"prompt")
    return tmp_path


def test_multi_backend_subsets_write_global_indices(project_root):
    """Each per-backend subset must name files by story-global index."""
    lines = [
        _line(0, "alpha", "first"),
        _line(1, "beta", "second"),
        _line(2, "alpha", "third"),
    ]
    qwen = FakeBackend("qwen")
    vibevoice = FakeBackend("vibevoice")

    # The multi-backend path in services.story_generation splits by backend
    # and generates each subset separately with concat=False.
    generate_story_audio(
        indexed_lines=[(0, lines[0]), (2, lines[2])],
        story_id="story",
        tts_backend=qwen,
        concat=False,
    )
    generate_story_audio(
        indexed_lines=[(1, lines[1])],
        story_id="story",
        tts_backend=vibevoice,
        concat=False,
    )

    out_dir = project_root / "outputs" / "story" / "story"
    assert sorted(f.name for f in out_dir.glob("*.wav")) == [
        "001_alpha.wav",
        "002_beta.wav",
        "003_alpha.wav",
    ]


def test_regenerate_indices_are_global(project_root):
    """Reuse bookkeeping must compare global indices against existing files."""
    indexed = [(0, _line(0, "alpha", "first")), (2, _line(2, "alpha", "third"))]
    backend = FakeBackend("qwen")
    generate_story_audio(
        indexed_lines=indexed, story_id="story", tts_backend=backend, concat=False
    )
    assert backend.generated == ["first", "third"]

    # Regenerate only global line 0; global line 2 must be reused from disk.
    rerun = FakeBackend("qwen")
    generate_story_audio(
        indexed_lines=indexed,
        story_id="story",
        tts_backend=rerun,
        concat=False,
        regenerate_indices={0},
    )
    assert rerun.generated == ["first"]
