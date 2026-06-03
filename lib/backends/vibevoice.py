"""VibeVoice TTS backend implementation."""

import json
from pathlib import Path
from typing import Any

import torch

from lib.backends.base import AudioResult, TTSBackend, VoicePrompt


class VibeVoiceBackend(TTSBackend):
    """VibeVoice TTS backend adapter using community fork.

    Uses vibevoice-community/VibeVoice for multi-speaker, long-form
    conversational audio generation with voice cloning.
    """

    def __init__(
        self,
        model_id: str = "vibevoice/VibeVoice-1.5B",
        device: str = "cuda:0",
        dtype: str = "float16",
        attn: str = "flash_attention_2",
        quantization: str | None = None,
        cfg_scale: float = 1.3,
        diffusion_steps: int = 10,
        **kwargs: Any,
    ):
        """Initialize VibeVoice backend.

        Args:
            model_id: HuggingFace model ID
            device: Device (cuda:0, cpu)
            dtype: Data type (float16, float32, bfloat16)
            attn: Attention implementation (flash_attention_2, sdpa)
            quantization: Quantization (4bit, 8bit, None)
            cfg_scale: Classifier-Free Guidance scale
            diffusion_steps: Number of DDPM steps
            **kwargs: Additional backend-specific parameters
        """
        self.model_id = model_id
        self.device = device
        self.dtype = dtype
        self.attn = attn
        self.quantization = quantization
        self.cfg_scale = cfg_scale
        self.diffusion_steps = diffusion_steps
        self.config = kwargs
        self._model: Any = None  # VibeVoiceForConditionalGenerationInference
        self._processor: Any = None  # VibeVoiceProcessor

    @property
    def backend_name(self) -> str:
        return "vibevoice"

    @property
    def model(self) -> Any:
        """Lazy-load model and processor."""
        if self._model is None:
            self._load_model()
        return self._model

    @property
    def processor(self) -> Any:
        """Get processor (loaded with model)."""
        if self._processor is None:
            self._load_model()
        return self._processor

    def _load_model(self) -> None:
        """Load VibeVoice model and processor."""
        from vibevoice.modular.modeling_vibevoice_inference import (  # type: ignore[import-not-found]
            VibeVoiceForConditionalGenerationInference,
        )
        from vibevoice.processor.vibevoice_processor import (  # type: ignore[import-not-found]
            VibeVoiceProcessor,
        )

        # Parse dtype
        torch_dtype = self._parse_dtype(self.dtype)

        # Load with quantization if specified
        kwargs: dict[str, Any] = {
            "torch_dtype": torch_dtype,
            "attn_implementation": self.attn,
        }

        if self.quantization == "4bit":
            kwargs["load_in_4bit"] = True
        elif self.quantization == "8bit":
            kwargs["load_in_8bit"] = True

        if self.device.startswith("cuda"):
            kwargs["device_map"] = self.device

        self._model = VibeVoiceForConditionalGenerationInference.from_pretrained(
            self.model_id, **kwargs
        )

        if not self.device.startswith("cuda"):
            self._model = self._model.to(self.device)

        self._model.eval()
        self._model.set_ddpm_inference_steps(num_steps=self.diffusion_steps)

        self._processor = VibeVoiceProcessor.from_pretrained(self.model_id)

    def _parse_dtype(self, dtype_str: str) -> torch.dtype:
        """Parse dtype string to torch dtype."""
        v = dtype_str.lower()
        if v in {"bfloat16", "bf16"}:
            return torch.bfloat16
        if v in {"float16", "fp16"}:
            return torch.float16
        if v in {"float32", "fp32"}:
            return torch.float32
        raise ValueError(f"Unsupported dtype: {dtype_str}")

    def generate_voice_design(
        self, text: str, language: str, instruction: str, **kwargs: Any
    ) -> AudioResult:
        """VibeVoice does not support voice design from text descriptions.

        Raises:
            NotImplementedError: Always raised as VibeVoice only supports voice cloning
        """
        raise NotImplementedError(
            "VibeVoice does not support voice design from text descriptions. "
            "Use voice cloning with reference audio instead. "
            "Create voices using the Qwen backend for voice design, "
            "then clone them with VibeVoice if needed."
        )

    def create_voice_clone_prompt(
        self, ref_audio: str | Path, ref_text: str | None, **kwargs: Any
    ) -> VoicePrompt:
        """Create voice clone prompt from reference audio.

        VibeVoice uses the reference audio directly during generation,
        so we just store metadata in the prompt.

        Args:
            ref_audio: Path to reference audio file
            ref_text: Optional reference transcript (not used by VibeVoice)
            **kwargs: Additional parameters

        Returns:
            VoicePrompt with reference audio metadata

        Raises:
            FileNotFoundError: If reference audio file doesn't exist
        """
        ref_audio_path = Path(ref_audio)

        if not ref_audio_path.exists():
            raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")

        # Store minimal metadata - actual processing happens during generation
        prompt_data = {
            "ref_audio_path": str(ref_audio_path),
            "ref_text": ref_text,
            "backend": "vibevoice",
            "model_id": self.model_id,
        }

        return VoicePrompt(
            backend="vibevoice",
            voice_id="",  # Set by caller
            data=prompt_data,
        )

    def generate_voice_clone(
        self, text: str, language: str, voice_prompt: VoicePrompt, **kwargs: Any
    ) -> AudioResult:
        """Generate speech using VibeVoice voice cloning.

        Args:
            text: Text to synthesize
            language: Target language (not used by VibeVoice)
            voice_prompt: Voice prompt from create_voice_clone_prompt()
            **kwargs: Additional parameters

        Returns:
            AudioResult with generated audio at 24kHz

        Raises:
            ValueError: If prompt backend doesn't match
            FileNotFoundError: If reference audio file doesn't exist
        """
        if voice_prompt.backend != "vibevoice":
            raise ValueError(f"Expected vibevoice prompt, got {voice_prompt.backend}")

        # Get reference audio path from prompt
        ref_audio_path = voice_prompt.data["ref_audio_path"]

        if not Path(ref_audio_path).exists():
            raise FileNotFoundError(f"Reference audio not found: {ref_audio_path}")

        # Format text as single-speaker script
        script = f"Speaker 1: {text}"

        # Prepare inputs
        inputs = self.processor(
            text=[script],
            voice_samples=[[ref_audio_path]],  # Single speaker
            padding=True,
            return_tensors="pt",
            return_attention_mask=True,
        )

        # Move to device
        for k, v in inputs.items():
            if torch.is_tensor(v):
                inputs[k] = v.to(self.device)

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=None,
                cfg_scale=self.cfg_scale,
                tokenizer=self.processor.tokenizer,
                generation_config={"do_sample": False},
                verbose=False,
                is_prefill=True,  # Enable voice cloning
            )

        # Extract audio
        audio_tensor = outputs.speech_outputs[0]  # First batch item

        # Convert to numpy
        if torch.is_tensor(audio_tensor):
            audio_np = audio_tensor.cpu().numpy()
        else:
            audio_np = audio_tensor

        return AudioResult(audio=audio_np, sample_rate=24000)

    def save_prompt(self, prompt: VoicePrompt, path: str | Path) -> None:
        """Save VibeVoice prompt to JSON.

        Args:
            prompt: Voice prompt to save
            path: Output file path

        Raises:
            IOError: If file cannot be written
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prompt.data, f, indent=2)

    def load_prompt(self, path: str | Path) -> VoicePrompt:
        """Load VibeVoice prompt from JSON.

        Args:
            path: Path to prompt file

        Returns:
            Loaded VoicePrompt

        Raises:
            FileNotFoundError: If prompt file doesn't exist
            ValueError: If prompt file format is invalid
        """
        path = Path(path)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if "backend" not in data or data["backend"] != "vibevoice":
            raise ValueError(f"Invalid VibeVoice prompt file: {path}")

        return VoicePrompt(
            backend="vibevoice",
            voice_id=path.stem,  # Extract from filename
            data=data,
        )
