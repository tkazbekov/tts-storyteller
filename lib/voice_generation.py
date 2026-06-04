"""Voice generation logic - generate WAV files and prompts for voices."""

import logging
from pathlib import Path

from lib.backends import TTSBackend
from lib.models import VoiceConfig
from lib.paths import get_prompt_path, get_voice_ref_audio_path
from lib.runtime import save_wav
from lib.voice_metadata import save_voice_metadata, should_regenerate_voice

logger = logging.getLogger(__name__)


def generate_voice_wav(
    voice_id: str,
    voice_config: VoiceConfig,
    tts_backend: TTSBackend,
) -> Path:
    """
    Generate reference audio WAV file for a voice.

    Args:
        voice_id: Voice identifier
        voice_config: Voice configuration (includes backend)
        tts_backend: VoiceDesign TTS backend

    Returns:
        Path to generated WAV file
    """
    backend = voice_config.backend
    wav_path = get_voice_ref_audio_path(voice_id, backend)
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate audio using VoiceDesign backend
    result = tts_backend.generate_voice_design(
        text=voice_config.sample_text,
        language=voice_config.language,
        instruction=voice_config.instruction,
    )

    # Save WAV file
    save_wav(str(wav_path), result.audio, result.sample_rate)
    return wav_path


def generate_voice_prompt(
    voice_id: str,
    ref_audio_path: Path,
    ref_text: str,
    tts_backend: TTSBackend,
    backend: str = "qwen",
    x_vector_only_mode: bool = False,
) -> Path:
    """
    Generate prompt file for a voice from reference audio.

    Args:
        voice_id: Voice identifier
        ref_audio_path: Path to reference audio WAV file
        ref_text: Reference text used for generation
        tts_backend: Base TTS backend
        backend: Backend type (qwen, vibevoice)
        x_vector_only_mode: Whether to use x-vector only mode

    Returns:
        Path to generated prompt file
    """
    prompt_path = get_prompt_path(voice_id, backend)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)

    if not ref_audio_path.exists():
        raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")

    # Generate prompt using Base backend
    voice_prompt = tts_backend.create_voice_clone_prompt(
        ref_audio=ref_audio_path,
        ref_text=ref_text if not x_vector_only_mode else None,
        x_vector_only_mode=x_vector_only_mode,
    )

    # Set voice_id and backend
    voice_prompt.voice_id = voice_id
    voice_prompt.backend = backend
    tts_backend.save_prompt(voice_prompt, prompt_path)
    return prompt_path


def generate_voice(
    voice_id: str,
    voice_config: VoiceConfig,
    voice_design_backend: TTSBackend,
    base_backend: TTSBackend,
    x_vector_only_mode: bool = False,
    force_regenerate: bool = False,
) -> tuple[Path, Path]:
    """
    Generate WAV and prompt files for a voice.

    This function checks metadata to determine if regeneration is needed.
    If the voice config hasn't changed, existing files are reused.

    Args:
        voice_id: Voice identifier
        voice_config: Voice configuration (includes backend)
        voice_design_backend: VoiceDesign TTS backend for WAV generation
        base_backend: Base TTS backend for prompt generation
        x_vector_only_mode: Whether to use x-vector only mode for prompt
        force_regenerate: Force regeneration even if config hasn't changed

    Returns:
        Tuple of (wav_path, prompt_path)
    """
    backend = voice_config.backend
    wav_path = get_voice_ref_audio_path(voice_id, backend)
    prompt_path = get_prompt_path(voice_id, backend)

    # Check if regeneration is needed
    regenerate_wav = force_regenerate or should_regenerate_voice(voice_id, voice_config)
    regenerate_prompt = (
        force_regenerate
        or not prompt_path.exists()
        or should_regenerate_voice(voice_id, voice_config)
    )

    # Generate WAV if needed
    if regenerate_wav or not wav_path.exists():
        logger.info("Generating WAV for voice '%s' using %s backend", voice_id, backend)
        wav_path = generate_voice_wav(voice_id, voice_config, voice_design_backend)
    else:
        logger.info("Reusing existing WAV for voice '%s'", voice_id)

    # Generate prompt if needed
    if regenerate_prompt or not prompt_path.exists():
        logger.info("Generating prompt for voice '%s' using %s backend", voice_id, backend)
        prompt_path = generate_voice_prompt(
            voice_id, wav_path, voice_config.sample_text, base_backend, backend, x_vector_only_mode
        )
    else:
        logger.info("Reusing existing prompt for voice '%s'", voice_id)

    # Save metadata for future incremental generation
    save_voice_metadata(voice_id, voice_config)

    return (wav_path, prompt_path)
