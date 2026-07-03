"""Runtime helpers shared across API and scripts."""

from __future__ import annotations

import json
import os
from typing import Any

import numpy as np
import soundfile as sf  # type: ignore[import-untyped]


def save_wav(path: str, wav: np.ndarray, sr: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, wav, sr)


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
