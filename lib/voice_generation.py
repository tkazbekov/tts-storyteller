"""Voice generation logic - generate WAV files and prompts for voices."""

from pathlib import Path

from qwen_tts import Qwen3TTSModel

from lib.models import VoiceConfig
from lib.paths import get_prompt_path, get_voice_ref_audio_path
from lib.runtime import save_prompt, save_wav
from lib.voice_metadata import save_voice_metadata, should_regenerate_voice


def generate_voice_wav(
    voice_id: str,
    voice_config: VoiceConfig,
    tts_model: Qwen3TTSModel,
) -> Path:
    """
    Generate reference audio WAV file for a voice.

    Args:
        voice_id: Voice identifier
        voice_config: Voice configuration
        tts_model: VoiceDesign TTS model

    Returns:
        Path to generated WAV file
    """
    wav_path = get_voice_ref_audio_path(voice_id)
    wav_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate audio using VoiceDesign model
    wavs, sr = tts_model.generate_voice_design(
        text=voice_config.sample_text,
        language=voice_config.language,
        instruct=voice_config.instruction,
    )

    # Save WAV file
    save_wav(str(wav_path), wavs[0], sr)
    return wav_path


def generate_voice_prompt(
    voice_id: str,
    ref_audio_path: Path,
    ref_text: str,
    tts_model: Qwen3TTSModel,
    x_vector_only_mode: bool = False,
) -> Path:
    """
    Generate prompt file for a voice from reference audio.

    Args:
        voice_id: Voice identifier
        ref_audio_path: Path to reference audio WAV file
        ref_text: Reference text used for generation
        tts_model: Base TTS model
        x_vector_only_mode: Whether to use x-vector only mode

    Returns:
        Path to generated prompt file
    """
    prompt_path = get_prompt_path(voice_id)
    prompt_path.parent.mkdir(parents=True, exist_ok=True)

    if not ref_audio_path.exists():
        raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")

    # Generate prompt using Base model
    items = tts_model.create_voice_clone_prompt(
        ref_audio=str(ref_audio_path),
        ref_text=ref_text if not x_vector_only_mode else None,
        x_vector_only_mode=x_vector_only_mode,
    )

    # Save prompt file
    save_prompt(str(prompt_path), items)
    return prompt_path


def generate_voice(
    voice_id: str,
    voice_config: VoiceConfig,
    voice_design_model: Qwen3TTSModel,
    base_model: Qwen3TTSModel,
    x_vector_only_mode: bool = False,
    force_regenerate: bool = False,
) -> tuple[Path, Path]:
    """
    Generate WAV and prompt files for a voice.

    This function checks metadata to determine if regeneration is needed.
    If the voice config hasn't changed, existing files are reused.

    Args:
        voice_id: Voice identifier
        voice_config: Voice configuration
        voice_design_model: VoiceDesign TTS model for WAV generation
        base_model: Base TTS model for prompt generation
        x_vector_only_mode: Whether to use x-vector only mode for prompt
        force_regenerate: Force regeneration even if config hasn't changed

    Returns:
        Tuple of (wav_path, prompt_path)
    """
    wav_path = get_voice_ref_audio_path(voice_id)
    prompt_path = get_prompt_path(voice_id)

    # Check if regeneration is needed
    regenerate_wav = force_regenerate or should_regenerate_voice(voice_id, voice_config)
    regenerate_prompt = (
        force_regenerate
        or not prompt_path.exists()
        or should_regenerate_voice(voice_id, voice_config)
    )

    # Generate WAV if needed
    if regenerate_wav or not wav_path.exists():
        print(f"[Voice] Generating WAV for voice '{voice_id}'...")
        wav_path = generate_voice_wav(voice_id, voice_config, voice_design_model)
    else:
        print(f"[Voice] Reusing existing WAV for voice '{voice_id}'")

    # Generate prompt if needed
    if regenerate_prompt or not prompt_path.exists():
        print(f"[Voice] Generating prompt for voice '{voice_id}'...")
        prompt_path = generate_voice_prompt(
            voice_id, wav_path, voice_config.sample_text, base_model, x_vector_only_mode
        )
    else:
        print(f"[Voice] Reusing existing prompt for voice '{voice_id}'")

    # Save metadata for future incremental generation
    save_voice_metadata(voice_id, voice_config)

    return (wav_path, prompt_path)
