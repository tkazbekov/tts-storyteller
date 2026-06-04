"""Qwen3-TTS backend implementation."""

from pathlib import Path
from typing import Any

import torch
from qwen_tts import Qwen3TTSModel, VoiceClonePromptItem

from lib.backends._torch_utils import detect_attn_impl, parse_dtype
from lib.backends.base import AudioResult, TTSBackend, VoicePrompt


class QwenTTSBackend(TTSBackend):
    """Qwen3-TTS backend adapter."""

    def __init__(
        self,
        model_id: str,
        device: str = "cuda:0",
        dtype: str = "bfloat16",
        attn: str = "auto",
    ):
        """Initialize Qwen backend.

        Args:
            model_id: Hugging Face model ID (e.g., "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
            device: Device to use (e.g., "cuda:0", "cpu")
            dtype: Data type (bfloat16, float16, float32)
            attn: Attention implementation (auto, none, flash_attention_2)
        """
        self.model_id = model_id
        self.device = device
        self.dtype = dtype
        self.attn = attn
        self._model: Qwen3TTSModel | None = None

    @property
    def backend_name(self) -> str:
        return "qwen"

    @property
    def supports_voice_design(self) -> bool:
        return True

    @property
    def requires_ref_text_for_clone(self) -> bool:
        return True

    @property
    def model(self) -> Qwen3TTSModel:
        """Lazy-load and cache the model."""
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> Qwen3TTSModel:
        """Load the Qwen3-TTS model."""
        torch_dtype = parse_dtype(self.dtype)
        attn_impl = detect_attn_impl(self.attn)

        kwargs: dict[str, Any] = {
            "device_map": self.device,
            "dtype": torch_dtype,
        }
        if attn_impl:
            kwargs["attn_implementation"] = attn_impl

        return Qwen3TTSModel.from_pretrained(self.model_id, **kwargs)

    def unload(self) -> None:
        """Release the model so its GPU/CPU memory can be reclaimed."""
        self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def generate_voice_design(
        self, text: str, language: str, instruction: str, **kwargs: Any
    ) -> AudioResult:
        """Generate designed voice using VoiceDesign model."""
        wavs, sr = self.model.generate_voice_design(
            text=text, language=language, instruct=instruction, **kwargs
        )
        return AudioResult(audio=wavs[0], sample_rate=sr)

    def create_voice_clone_prompt(
        self, ref_audio: str | Path, ref_text: str | None, **kwargs: Any
    ) -> VoicePrompt:
        """Create voice clone prompt from reference audio."""
        items = self.model.create_voice_clone_prompt(
            ref_audio=str(ref_audio), ref_text=ref_text, **kwargs
        )

        # Serialize Qwen-specific prompt items
        serialized_items = []
        for item in items:
            item_dict = {
                "ref_code": item.ref_code.tolist() if item.ref_code is not None else None,
                "ref_spk_embedding": item.ref_spk_embedding.tolist(),
                "x_vector_only_mode": item.x_vector_only_mode,
                "icl_mode": item.icl_mode,
                "ref_text": item.ref_text,
            }
            serialized_items.append(item_dict)

        return VoicePrompt(
            backend="qwen",
            voice_id="",
            data={"items": serialized_items},  # Will be set by caller
        )

    def generate_voice_clone(
        self, text: str, language: str, voice_prompt: VoicePrompt, **kwargs: Any
    ) -> AudioResult:
        """Generate speech using voice cloning."""
        if voice_prompt.backend != "qwen":
            raise ValueError(f"Expected qwen prompt, got {voice_prompt.backend}")

        # Deserialize prompt items
        items = self._deserialize_prompt_items(voice_prompt.data["items"])

        wavs, sr = self.model.generate_voice_clone(
            text=text, language=language, voice_clone_prompt=items, **kwargs
        )
        return AudioResult(audio=wavs[0], sample_rate=sr)

    def _deserialize_prompt_items(self, items_data: list[dict]) -> list[VoiceClonePromptItem]:
        """Deserialize prompt items from dict format."""
        items: list[VoiceClonePromptItem] = []
        for d in items_data:
            ref_code = d.get("ref_code", None)
            if ref_code is not None:
                ref_code = torch.tensor(ref_code)

            ref_spk = torch.tensor(d["ref_spk_embedding"])

            items.append(
                VoiceClonePromptItem(
                    ref_code=ref_code,
                    ref_spk_embedding=ref_spk,
                    x_vector_only_mode=bool(d.get("x_vector_only_mode", False)),
                    icl_mode=bool(d.get("icl_mode", True)),
                    ref_text=d.get("ref_text", None),
                )
            )
        return items

    def save_prompt(self, prompt: VoicePrompt, path: str | Path) -> None:
        """Save prompt to disk in Qwen's .pt format."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Use torch.save for backward compatibility with existing .pt files
        torch.save(prompt.data, str(path))

    def load_prompt(self, path: str | Path) -> VoicePrompt:
        """Load prompt from disk."""
        data = torch.load(str(path), map_location="cpu", weights_only=True)

        if not isinstance(data, dict) or "items" not in data:
            raise ValueError(f"Invalid prompt file format: {path}")

        return VoicePrompt(
            backend="qwen",
            voice_id=Path(path).stem,  # Extract voice_id from filename
            data=data,
        )
