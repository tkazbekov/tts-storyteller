"""TTS generation logic for story templates."""

import subprocess
from pathlib import Path

from qwen_tts import Qwen3TTSModel

from lib.models import ResolvedLine
from lib.paths import get_prompt_path, get_story_output_dir
from scripts.common import load_prompt, load_tts_model, save_wav


def generate_story_audio(
    resolved_lines: list[ResolvedLine],
    story_id: str,
    tts_model: Qwen3TTSModel | None = None,
    model_id: str = "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    device: str = "cuda:0",
    dtype: str = "bfloat16",
    attn: str = "auto",
    language: str = "English",
    concat: bool = True,
) -> Path:
    """
    Generate audio for a story from resolved lines.

    Args:
        resolved_lines: List of resolved lines with voice assignments
        story_id: Story identifier (used for output directory)
        tts_model: Optional pre-loaded TTS model instance (for caching)
        model_id: TTS model ID (used if tts_model is None)
        device: Device to use (e.g., "cuda:0" or "cpu")
        dtype: Data type (bf16|fp16|fp32)
        attn: Attention implementation (auto|none|flash_attention_2)
        language: Language for generation (defaults to English)
        concat: Whether to concatenate outputs into one WAV

    Returns:
        Path to the concatenated audio file (if concat=True) or directory with individual files

    Raises:
        FileNotFoundError: If prompt files are missing
        RuntimeError: If sox is not available and concat=True
    """
    if not resolved_lines:
        raise ValueError("No lines to generate")

    # Use provided model or load new one
    if tts_model is None:
        tts = load_tts_model(model_id, device, dtype, attn)
    else:
        tts = tts_model

    # Setup output directory
    out_dir = get_story_output_dir(story_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Generate audio for each line
    out_files: list[str] = []
    prompt_cache: dict[str, list] = {}

    for idx, resolved_line in enumerate(resolved_lines, start=1):
        voice_id = resolved_line.voiceId
        text = resolved_line.line

        # Load prompt if not cached
        if voice_id not in prompt_cache:
            prompt_path = get_prompt_path(voice_id)
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            prompt_cache[voice_id] = load_prompt(str(prompt_path))

        # Generate audio
        wavs, sr = tts.generate_voice_clone(
            text=text,
            language=language,
            voice_clone_prompt=prompt_cache[voice_id],
        )

        # Save individual line audio
        out_path = out_dir / f"{idx:03d}_{voice_id}.wav"
        save_wav(str(out_path), wavs[0], sr)
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
