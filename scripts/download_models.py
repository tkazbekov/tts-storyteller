#!/usr/bin/env python3
"""Pre-download configured Hugging Face model snapshots.

This only warms the local Hugging Face cache. Runtime code still lazy-loads model
classes when generation starts.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from huggingface_hub import snapshot_download

from lib.config import get_config
from lib.env import load_env


@dataclass(frozen=True)
class ModelToDownload:
    backend: str
    purpose: str
    model_id: str


def _enabled_models(backend: str) -> list[ModelToDownload]:
    cfg = get_config()
    models: list[ModelToDownload] = []

    if backend in {"qwen", "all"}:
        models.extend(
            [
                ModelToDownload("qwen", "base", cfg.qwen_base.model_id),
                ModelToDownload("qwen", "voice_design", cfg.qwen_voice_design.model_id),
            ]
        )

    if backend in {"vibevoice", "all"}:
        models.append(ModelToDownload("vibevoice", "base", cfg.vibevoice_base.model_id))
        # VibeVoice voice design is not currently supported; do not download it by default.

    seen: set[str] = set()
    unique: list[ModelToDownload] = []
    for model in models:
        if model.model_id not in seen:
            unique.append(model)
            seen.add(model.model_id)
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="Download configured TTS model snapshots")
    parser.add_argument(
        "--backend",
        choices=["qwen", "vibevoice", "all"],
        default=os.getenv("TTS_DEFAULT_BACKEND", "qwen"),
        help="Which backend models to download",
    )
    parser.add_argument(
        "--local-dir",
        default=None,
        help="Optional explicit target directory. Defaults to Hugging Face cache.",
    )
    args = parser.parse_args()

    load_env()

    for model in _enabled_models(args.backend):
        print(f"Downloading {model.backend}/{model.purpose}: {model.model_id}")
        path = snapshot_download(
            repo_id=model.model_id,
            local_dir=args.local_dir,
            resume_download=True,
        )
        print(f"  cached at: {path}")


if __name__ == "__main__":
    main()
