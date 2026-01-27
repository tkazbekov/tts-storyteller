"""Metadata storage for voice generation - stores voice config hashes."""

import hashlib
import json

from lib.models import VoiceConfig
from lib.paths import get_voice_metadata_path


def compute_voice_hash(voice_config: VoiceConfig) -> str:
    """
    Compute a hash for a voice config to detect changes.

    A voice is considered changed if:
    - The id changes
    - The language changes
    - The instruction changes
    - The sample_text changes
    """
    # Create a stable string representation
    config_str = f"{voice_config.id}|{voice_config.language}|{voice_config.instruction}|{voice_config.sample_text}"
    return hashlib.sha256(config_str.encode()).hexdigest()[:16]


def load_voice_metadata() -> dict[str, dict[str, str]]:
    """
    Load voice metadata from file.

    Returns:
        Dictionary mapping voice_id to metadata dict with 'hash' and 'language' keys,
        or empty dict if metadata doesn't exist
    """
    metadata_path = get_voice_metadata_path()

    if not metadata_path.exists():
        return {}

    try:
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
        if not isinstance(metadata, dict):
            return {}
        return metadata
    except (json.JSONDecodeError, KeyError):
        return {}


def save_voice_metadata(voice_id: str, voice_config: VoiceConfig) -> None:
    """
    Save voice metadata (hash and language) to metadata file.

    Args:
        voice_id: Voice identifier
        voice_config: Voice configuration
    """
    metadata_path = get_voice_metadata_path()
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing metadata
    metadata = load_voice_metadata()

    # Compute hash and update metadata
    voice_hash = compute_voice_hash(voice_config)
    metadata[voice_id] = {
        "hash": voice_hash,
        "language": voice_config.language,
    }

    # Save back to file
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)


def should_regenerate_voice(voice_id: str, voice_config: VoiceConfig) -> bool:
    """
    Check if a voice should be regenerated based on config changes.

    Args:
        voice_id: Voice identifier
        voice_config: Current voice configuration

    Returns:
        True if voice should be regenerated (config changed or no metadata exists),
        False if config hasn't changed
    """
    metadata = load_voice_metadata()

    if voice_id not in metadata:
        # No previous metadata - regenerate
        return True

    old_hash = metadata[voice_id].get("hash")
    if old_hash is None:
        # Invalid metadata - regenerate
        return True

    current_hash = compute_voice_hash(voice_config)
    return old_hash != current_hash
