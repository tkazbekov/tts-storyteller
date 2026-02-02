#!/usr/bin/env python3
"""Compatibility helpers for CLI scripts."""

from lib.runtime import (
    load_prompt,
    load_tts_model,
    read_json,
    save_prompt,
    save_wav,
    write_json,
)

__all__ = [
    "load_prompt",
    "load_tts_model",
    "read_json",
    "save_prompt",
    "save_wav",
    "write_json",
]
