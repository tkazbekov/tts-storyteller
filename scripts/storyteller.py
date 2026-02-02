#!/usr/bin/env python3
"""Generate a multi-voice story from a stored template."""

import argparse
import sys

from lib.env import load_env
from lib.generation import generate_story_audio
from lib.repositories import get_story_repository, get_voice_repository
from lib.resolution import resolve_story

DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


load_env()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a multi-voice story from a JSON template."
    )
    parser.add_argument(
        "--story", required=True, help="Story ID (filename without .json extension)"
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Base model id")
    parser.add_argument("--device", default="cuda:0", help="Device map, e.g. cuda:0 or cpu")
    parser.add_argument("--dtype", default="bfloat16", help="bf16|fp16|fp32")
    parser.add_argument("--attn", default="auto", help="auto|none|flash_attention_2")
    parser.add_argument("--language", default="English", help="Language for generation")
    parser.add_argument("--no-concat", action="store_true", help="Don't concatenate outputs")
    args = parser.parse_args()

    try:
        # Load story via repository
        story = get_story_repository().get(args.story)

        # Resolve roles to voices
        available_voices = get_voice_repository().get_available_ids()
        resolved_lines = resolve_story(story, available_voices)

        # Generate audio
        output_path = generate_story_audio(
            resolved_lines=resolved_lines,
            story_id=args.story,
            model=args.model,
            device=args.device,
            dtype=args.dtype,
            attn=args.attn,
            language=args.language,
            concat=not args.no_concat,
        )

        if args.no_concat:
            print(f"Generated audio files in: {output_path}")
        else:
            print(f"Generated concatenated audio: {output_path}")

        return 0

    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except KeyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
