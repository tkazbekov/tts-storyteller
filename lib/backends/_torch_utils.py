"""Shared torch helpers used by the TTS backends."""

from __future__ import annotations

import torch


def parse_dtype(dtype_str: str) -> torch.dtype:
    """Parse a dtype string (e.g. "bf16", "float16") into a torch.dtype."""
    v = dtype_str.lower()
    if v in {"bfloat16", "bf16"}:
        return torch.bfloat16
    if v in {"float16", "fp16"}:
        return torch.float16
    if v in {"float32", "fp32"}:
        return torch.float32
    raise ValueError(f"Unsupported dtype: {dtype_str}")


def detect_attn_impl(requested: str) -> str | None:
    """Resolve the attention implementation for a requested setting.

    "auto" uses flash-attention 2 when the package is importable, otherwise
    falls back to the model default (None).
    """
    if requested == "none":
        return None
    if requested == "auto":
        try:
            import flash_attn  # type: ignore[import-untyped] # noqa: F401

            return "flash_attention_2"
        except ImportError:
            return None
    if requested == "flash_attention_2":
        return "flash_attention_2"
    raise ValueError("attn must be one of: auto, none, flash_attention_2")
