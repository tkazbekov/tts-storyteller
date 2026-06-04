#!/usr/bin/env python3
"""Test VibeVoice backend implementation."""

import argparse
import sys
from pathlib import Path

import soundfile as sf  # type: ignore[import-untyped]

from lib.backend_factory import TTSBackendFactory


def main():
    parser = argparse.ArgumentParser(
        description="Test VibeVoice backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with Qwen-generated reference audio
  python examples/vibevoice_smoke.py \\
    --ref-audio outputs/voice_design/qwen/narrator_male.wav \\
    --text "Testing VibeVoice backend integration"

  # Test with 7B model
  python examples/vibevoice_smoke.py \\
    --ref-audio reference.wav \\
    --text "Hello world" \\
    --model vibevoice/VibeVoice-7B

  # Test with CPU (slower)
  python examples/vibevoice_smoke.py \\
    --ref-audio reference.wav \\
    --device cpu
        """,
    )
    parser.add_argument(
        "--ref-audio",
        type=Path,
        required=True,
        help="Reference audio WAV file for voice cloning",
    )
    parser.add_argument(
        "--text",
        type=str,
        default="Hello, this is a test of the VibeVoice backend.",
        help="Text to generate",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("vibevoice_test.wav"),
        help="Output audio file path",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="vibevoice/VibeVoice-1.5B",
        help="Model ID (vibevoice/VibeVoice-1.5B or vibevoice/VibeVoice-7B)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda:0",
        help="Device (cuda:0, cpu)",
    )
    parser.add_argument(
        "--dtype",
        type=str,
        default="float16",
        help="Data type (float16, float32, bfloat16)",
    )
    parser.add_argument(
        "--quantization",
        type=str,
        default="4bit",
        choices=["4bit", "8bit", "none"],
        help="Quantization level",
    )
    parser.add_argument(
        "--cfg-scale",
        type=float,
        default=1.3,
        help="Classifier-Free Guidance scale",
    )
    parser.add_argument(
        "--diffusion-steps",
        type=int,
        default=10,
        help="Number of diffusion steps",
    )
    args = parser.parse_args()

    # Validate reference audio exists
    if not args.ref_audio.exists():
        print(f"Error: Reference audio not found: {args.ref_audio}", file=sys.stderr)
        return 1

    # Convert quantization
    quantization = None if args.quantization == "none" else args.quantization

    print("=" * 60)
    print("VibeVoice Backend Test")
    print("=" * 60)
    print(f"Model:            {args.model}")
    print(f"Device:           {args.device}")
    print(f"Data type:        {args.dtype}")
    print(f"Quantization:     {args.quantization}")
    print(f"CFG scale:        {args.cfg_scale}")
    print(f"Diffusion steps:  {args.diffusion_steps}")
    print(f"Reference audio:  {args.ref_audio}")
    print(f"Text:             {args.text}")
    print(f"Output:           {args.output}")
    print("=" * 60)

    try:
        print("\n[1/4] Creating VibeVoice backend...")
        backend = TTSBackendFactory.create(
            backend_type="vibevoice",
            model_id=args.model,
            device=args.device,
            dtype=args.dtype,
            quantization=quantization,
            cfg_scale=args.cfg_scale,
            diffusion_steps=args.diffusion_steps,
        )
        print("✓ Backend created")

        print("\n[2/4] Creating voice prompt from reference audio...")
        prompt = backend.create_voice_clone_prompt(
            ref_audio=args.ref_audio,
            ref_text=None,
        )
        print(f"✓ Voice prompt created (backend: {prompt.backend})")

        print("\n[3/4] Generating speech...")
        print("  (This may take 5-10 seconds depending on text length)")
        result = backend.generate_voice_clone(
            text=args.text,
            language="English",
            voice_prompt=prompt,
        )
        print(f"✓ Speech generated ({len(result.audio)} samples at {result.sample_rate}Hz)")
        duration = len(result.audio) / result.sample_rate
        print(f"  Duration: {duration:.2f} seconds")

        print("\n[4/4] Saving audio...")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(args.output, result.audio, result.sample_rate)
        print(f"✓ Saved to: {args.output}")

        print("\n" + "=" * 60)
        print("SUCCESS! VibeVoice backend is working correctly.")
        print("=" * 60)
        return 0

    except ImportError as e:
        print(f"\n✗ Import error: {e}", file=sys.stderr)
        print("\nPlease install VibeVoice dependencies:", file=sys.stderr)
        print("  pip install -r requirements-vibevoice.txt", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
