"""TTS generation logic for story templates."""

import subprocess
from pathlib import Path
from typing import Any

from lib.backends import TTSBackend
from lib.incremental import get_existing_audio_files
from lib.models import ResolvedLine
from lib.paths import get_prompt_path, get_story_output_dir
from lib.runtime import save_wav


def generate_story_audio(
    resolved_lines: list[ResolvedLine],
    story_id: str,
    tts_backend: TTSBackend | None = None,
    language: str = "English",
    concat: bool = True,
    regenerate_indices: set[int] | None = None,
) -> Path:
    """
    Generate audio for a story from resolved lines.

    Args:
        resolved_lines: List of resolved lines with voice assignments
        story_id: Story identifier (used for output directory)
        tts_backend: Optional pre-loaded TTS backend instance (for caching)
        language: Language for generation (defaults to English)
        concat: Whether to concatenate outputs into one WAV
        regenerate_indices: Optional set of 0-based line indices to regenerate.
            If None, all lines are generated. If provided, only these indices
            are regenerated; other lines reuse existing files if available.

    Returns:
        Path to the concatenated audio file (if concat=True) or directory with individual files

    Raises:
        FileNotFoundError: If prompt files are missing
        RuntimeError: If sox is not available and concat=True
        ValueError: If no backend provided and can't create default
    """
    if not resolved_lines:
        raise ValueError("No lines to generate")

    # Use provided backend or create default
    if tts_backend is None:
        from lib.backend_factory import TTSBackendFactory

        tts_backend = TTSBackendFactory.create()

    # Setup output directory
    out_dir = get_story_output_dir(story_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Get existing audio files if doing incremental generation
    existing_files: dict[int, Path] = {}
    if regenerate_indices is not None:
        existing_files = get_existing_audio_files(story_id)

    # Generate audio for each line
    out_files: list[str] = []
    prompt_cache: dict[str, Any] = {}

    for idx, resolved_line in enumerate(resolved_lines):
        # Check if we should reuse existing file
        if regenerate_indices is not None and idx not in regenerate_indices:
            # Try to reuse existing file
            if idx in existing_files:
                out_files.append(str(existing_files[idx]))
                continue
            # If no existing file, we need to generate it
            # (this handles new lines that don't have existing files)

        voice_id = resolved_line.voiceId
        text = resolved_line.line

        # Load prompt if not cached
        if voice_id not in prompt_cache:
            # Try to get prompt path with backend from tts_backend
            backend_name = tts_backend.backend_name
            prompt_path = get_prompt_path(voice_id, backend_name)
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            prompt_cache[voice_id] = tts_backend.load_prompt(prompt_path)

        # Generate audio
        result = tts_backend.generate_voice_clone(
            text=text,
            language=language,
            voice_prompt=prompt_cache[voice_id],
        )

        # Save individual line audio (1-based index for filename)
        out_path = out_dir / f"{idx + 1:03d}_{voice_id}.wav"
        save_wav(str(out_path), result.audio, result.sample_rate)
        out_files.append(str(out_path))

    # Concatenate if requested
    if concat:
        sox_path = "sox"
        try:
            subprocess.run(
                [sox_path, "--version"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            raise RuntimeError("sox not found in PATH; cannot concatenate audio") from e

        concat_out = out_dir / "story_full.wav"
        concat_wavs(sox_path, out_files, str(concat_out))
        return concat_out

    return out_dir


def concat_wavs(sox_path: str, wavs: list[str], out_path: str) -> None:
    """Concatenate WAV files using sox."""
    cmd = [sox_path] + wavs + [out_path]
    subprocess.run(cmd, check=True)
