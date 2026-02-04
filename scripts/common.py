#!/usr/bin/env python3
"""Compatibility helpers for CLI scripts."""

from lib.backend_factory import TTSBackendFactory
from lib.runtime import read_json, save_wav, write_json

__all__ = [
    "TTSBackendFactory",
    "read_json",
    "save_wav",
    "write_json",
]
