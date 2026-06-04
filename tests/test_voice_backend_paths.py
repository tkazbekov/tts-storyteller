"""Regression tests for backend-aware voice metadata and audio paths."""

from __future__ import annotations

import json

import pytest

from lib.backends.base import VoicePrompt
from lib.models import VoiceCloneConfig, VoiceConfig


class FakeBackend:
    """Minimal backend that can create and save clone prompts without loading models."""

    backend_name = "vibevoice"

    def create_voice_clone_prompt(self, ref_audio, ref_text=None, x_vector_only_mode=False):
        return VoicePrompt(
            backend="vibevoice",
            voice_id="vv_clone",
            data={
                "backend": "vibevoice",
                "ref_audio_path": str(ref_audio),
                "ref_text": ref_text,
                "x_vector_only_mode": x_vector_only_mode,
            },
        )

    def save_prompt(self, voice_prompt, prompt_path):
        prompt_path.write_text(json.dumps(voice_prompt.data), encoding="utf-8")


class FakeVoiceRepository:
    def __init__(self):
        self.saved: tuple[str, VoiceConfig] | None = None

    async def save(self, voice_id: str, voice_config: VoiceConfig) -> None:
        self.saved = (voice_id, voice_config)


@pytest.mark.asyncio
async def test_clone_job_copies_reference_audio_to_backend_specific_sample_path(
    tmp_path, monkeypatch
):
    import services.voice_generation as voice_generation_service
    from lib import paths

    monkeypatch.setattr(paths, "PROJECT_ROOT", tmp_path)
    paths.ensure_backend_directories()

    upload_dir = tmp_path / "uploads" / "reference_audio"
    upload_dir.mkdir(parents=True)
    uploaded = upload_dir / "source.wav"
    uploaded.write_bytes(b"RIFFuploaded")

    fake_repo = FakeVoiceRepository()
    monkeypatch.setattr(
        voice_generation_service, "get_backend", lambda backend, purpose: FakeBackend()
    )
    monkeypatch.setattr(voice_generation_service, "get_voice_repository", lambda: fake_repo)

    prompt_path = await voice_generation_service.generate_voice_clone_job(
        "vv_clone",
        VoiceCloneConfig(
            id="vv_clone",
            language="English",
            instruction="Warm narrator",
            ref_audio_url=str(uploaded),
            ref_text="reference transcript",
            backend="vibevoice",
        ),
    )

    expected_prompt = paths.get_prompt_path("vv_clone", "vibevoice")
    expected_audio = paths.get_voice_ref_audio_path("vv_clone", "vibevoice")

    assert prompt_path == expected_prompt
    assert expected_prompt.exists()
    assert expected_audio.read_bytes() == b"RIFFuploaded"
    assert fake_repo.saved is not None
    assert fake_repo.saved[1].backend == "vibevoice"
