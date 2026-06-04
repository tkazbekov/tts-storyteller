"""Runtime helpers shared across API and scripts."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

import numpy as np
import soundfile as sf  # type: ignore[import-untyped]
import torch
from qwen_tts import Qwen3TTSModel, VoiceClonePromptItem

from lib.backends._torch_utils import detect_attn_impl, parse_dtype


def load_tts_model(model_id: str, device: str, dtype: str, attn: str) -> Qwen3TTSModel:
    torch_dtype = parse_dtype(dtype)
    attn_impl = detect_attn_impl(attn)
    kwargs: dict[str, Any] = {
        "device_map": device,
        "dtype": torch_dtype,
    }
    if attn_impl:
        kwargs["attn_implementation"] = attn_impl
    return Qwen3TTSModel.from_pretrained(model_id, **kwargs)


def save_wav(path: str, wav: np.ndarray, sr: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, wav, sr)


def save_prompt(path: str, items: list[VoiceClonePromptItem]) -> None:
    payload = {"items": [asdict(it) for it in items]}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(payload, path)


def load_prompt(path: str) -> list[VoiceClonePromptItem]:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or "items" not in payload:
        raise ValueError("Invalid prompt file format")
    items_raw = payload["items"]
    if not isinstance(items_raw, list) or len(items_raw) == 0:
        raise ValueError("Prompt file has no items")
    items: list[VoiceClonePromptItem] = []
    for d in items_raw:
        if not isinstance(d, dict):
            raise ValueError("Prompt item is not a dict")
        ref_code = d.get("ref_code", None)
        if ref_code is not None and not torch.is_tensor(ref_code):
            ref_code = torch.tensor(ref_code)
        ref_spk = d.get("ref_spk_embedding", None)
        if ref_spk is None:
            raise ValueError("Prompt item missing ref_spk_embedding")
        if not torch.is_tensor(ref_spk):
            ref_spk = torch.tensor(ref_spk)
        items.append(
            VoiceClonePromptItem(
                ref_code=ref_code,
                ref_spk_embedding=ref_spk,
                x_vector_only_mode=bool(d.get("x_vector_only_mode", False)),
                icl_mode=bool(d.get("icl_mode", not bool(d.get("x_vector_only_mode", False)))),
                ref_text=d.get("ref_text", None),
            )
        )
    return items


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
