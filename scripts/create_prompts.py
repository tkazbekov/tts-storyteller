#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

from lib.backend_factory import TTSBackendFactory
from lib.paths import get_prompt_extension
from lib.runtime import read_json, write_json

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create reusable voice prompts from reference audio."
    )
    parser.add_argument("--config", default="voices/voices.json", help="Path to voices config JSON")
    parser.add_argument("--out-dir", default=None, help="Prompt output directory")
    parser.add_argument("--backend", default="qwen", help="TTS backend to use: qwen or vibevoice")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Base model id")
    parser.add_argument("--device", default="cuda:0", help="Device map, e.g. cuda:0 or cpu")
    parser.add_argument("--dtype", default="bfloat16", help="bf16|fp16|fp32")
    parser.add_argument("--attn", default="auto", help="auto|none|flash_attention_2")
    parser.add_argument("--xvec-only", action="store_true", help="Use x-vector only mode")
    args = parser.parse_args()

    out_dir = Path(args.out_dir or Path("prompts") / args.backend)
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_ext = get_prompt_extension(args.backend)

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

    meta_out = []
    for v in voices:
        if not isinstance(v, dict):
            raise SystemExit("Each voice entry must be an object")
        voice_id = v.get("id")
        ref_audio = v.get("ref_audio")
        if not ref_audio and voice_id:
            ref_audio = os.path.join("outputs", "voice_design", args.backend, f"{voice_id}.wav")
        ref_text = v.get("ref_text", v.get("sample_text"))
        if not voice_id or not ref_audio:
            raise SystemExit("Each voice needs id and a reference audio path")
        if not os.path.exists(ref_audio):
            raise SystemExit(f"Reference audio not found: {ref_audio}")
        if not args.xvec_only and backend.requires_ref_text_for_clone and not ref_text:
            raise SystemExit("ref_text is required for this backend when not using x-vector only")

        voice_prompt = backend.create_voice_clone_prompt(
            ref_audio=ref_audio,
            ref_text=ref_text,
            x_vector_only_mode=bool(args.xvec_only),
        )
        voice_prompt.voice_id = voice_id
        out_path = out_dir / f"{voice_id}{prompt_ext}"
        backend.save_prompt(voice_prompt, out_path)
        print(f"Wrote {out_path}")

        meta_out.append(
            {
                "id": voice_id,
                "backend": args.backend,
                "prompt_path": str(out_path),
                "ref_audio": ref_audio,
                "ref_text": ref_text,
                "x_vector_only_mode": bool(args.xvec_only),
            }
        )

    write_json(out_dir / "prompts_meta.json", meta_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
