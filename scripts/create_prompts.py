#!/usr/bin/env python3
import argparse
import os

from common import load_tts_model, read_json, save_prompt, write_json

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create reusable voice prompts from reference audio."
    )
    parser.add_argument("--config", default="voices/voices.json", help="Path to voices config JSON")
    parser.add_argument("--out-dir", default="prompts", help="Directory for .pt prompt files")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Base model id")
    parser.add_argument("--device", default="cuda:0", help="Device map, e.g. cuda:0 or cpu")
    parser.add_argument("--dtype", default="bfloat16", help="bf16|fp16|fp32")
    parser.add_argument("--attn", default="auto", help="auto|none|flash_attention_2")
    parser.add_argument("--xvec-only", action="store_true", help="Use x-vector only mode")
    args = parser.parse_args()

    voices = read_json(args.config)
    if not isinstance(voices, list):
        raise SystemExit("voices.json must be a list")

    tts = load_tts_model(args.model, args.device, args.dtype, args.attn)

    meta_out = []
    for v in voices:
        if not isinstance(v, dict):
            raise SystemExit("Each voice entry must be an object")
        voice_id = v.get("id")
        ref_audio = v.get("ref_audio")
        if not ref_audio and voice_id:
            ref_audio = os.path.join("outputs", "voice_design", f"{voice_id}.wav")
        ref_text = v.get("ref_text", v.get("sample_text"))
        if not voice_id or not ref_audio:
            raise SystemExit("Each voice needs id and a reference audio path")
        if not os.path.exists(ref_audio):
            raise SystemExit(f"Reference audio not found: {ref_audio}")
        if not args.xvec_only and not ref_text:
            raise SystemExit("ref_text is required when not using x-vector only")

        items = tts.create_voice_clone_prompt(
            ref_audio=ref_audio,
            ref_text=ref_text,
            x_vector_only_mode=bool(args.xvec_only),
        )
        out_path = os.path.join(args.out_dir, f"{voice_id}.pt")
        save_prompt(out_path, items)
        print(f"Wrote {out_path}")

        meta_out.append(
            {
                "id": voice_id,
                "prompt_path": out_path,
                "ref_audio": ref_audio,
                "ref_text": ref_text,
                "x_vector_only_mode": bool(args.xvec_only),
            }
        )

    write_json(os.path.join(args.out_dir, "prompts_meta.json"), meta_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
