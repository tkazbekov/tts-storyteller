#!/usr/bin/env python3
import argparse
from pathlib import Path

from lib.backend_factory import TTSBackendFactory
from lib.runtime import read_json, save_wav, write_json

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate designed voices from a config file.")
    parser.add_argument("--config", default="voices/voices.json", help="Path to voices config JSON")
    parser.add_argument("--out-dir", default=None, help="Directory for generated WAV files")
    parser.add_argument("--backend", default="qwen", help="TTS backend to use: qwen")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="VoiceDesign model id")
    parser.add_argument("--device", default="cuda:0", help="Device map, e.g. cuda:0 or cpu")
    parser.add_argument("--dtype", default="bfloat16", help="bf16|fp16|fp32")
    parser.add_argument("--attn", default="auto", help="auto|none|flash_attention_2")
    parser.add_argument("--max-new-tokens", type=int, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir or Path("outputs") / "voice_design" / args.backend)
    out_dir.mkdir(parents=True, exist_ok=True)

    voices = read_json(args.config)
    if not isinstance(voices, list):
        raise SystemExit("voices.json must be a list")

    backend = TTSBackendFactory.create(
        backend_type=args.backend,
        model_id=args.model,
        device=args.device,
        dtype=args.dtype,
        attn=args.attn,
    )

    if not backend.supports_voice_design:
        raise SystemExit(f"Voice design from text is not supported by the '{args.backend}' backend")

    meta_out = []
    for v in voices:
        if not isinstance(v, dict):
            raise SystemExit("Each voice entry must be an object")
        voice_id = v.get("id")
        text = v.get("sample_text")
        instruct = v.get("instruction")
        language = v.get("language", "Auto")
        if not voice_id or not text or not instruct:
            raise SystemExit("Each voice needs id, sample_text, instruction")

        kwargs: dict[str, object] = {}
        if args.max_new_tokens is not None:
            kwargs["max_new_tokens"] = args.max_new_tokens

        result = backend.generate_voice_design(
            text=text,
            language=language,
            instruction=instruct,
            **kwargs,
        )
        out_path = out_dir / f"{voice_id}.wav"
        save_wav(out_path, result.audio, result.sample_rate)

        meta_out.append(
            {
                "id": voice_id,
                "backend": args.backend,
                "language": language,
                "instruction": instruct,
                "sample_text": text,
                "ref_audio": str(out_path),
                "ref_text": text,
            }
        )
        print(f"Wrote {out_path}")

    write_json(out_dir / "voice_design_meta.json", meta_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
