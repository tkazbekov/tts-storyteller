#!/usr/bin/env python3
"""Convert old .txt story format to JSON template format."""

import argparse
import json
from pathlib import Path

from lib.models import Role, StoryLine, StoryTemplate
from lib.paths import get_stories_dir
from lib.validation import validate_story


def parse_txt_story(txt_path: Path) -> StoryTemplate:
    """
    Parse old .txt format into StoryTemplate.

    Format: voice_id|language|text (one per line)
    Comments starting with # are ignored.
    """
    lines_data: list[tuple[str, str, str]] = []  # (voice_id, language, text)
    seen_voices: set[str] = set()

    with open(txt_path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split("|", 2)
            if len(parts) < 2:
                raise ValueError(
                    f"Line {line_num}: Invalid format, expected 'voice_id|language|text'"
                )

            voice_id = parts[0].strip()
            language = parts[1].strip() if len(parts) > 1 else "English"
            text = parts[2].strip() if len(parts) > 2 else ""

            if not voice_id or not text:
                raise ValueError(f"Line {line_num}: Missing voice_id or text")

            lines_data.append((voice_id, language, text))
            seen_voices.add(voice_id)

    if not lines_data:
        raise ValueError("No valid lines found in file")

    # Create roles from unique voice_ids
    voice_list = sorted(seen_voices)
    roles: list[Role] = []
    voice_to_role_id: dict[str, int] = {}

    for role_id, voice_id in enumerate(voice_list):
        # Generate role name from voice_id (capitalize, replace underscores)
        role_name = voice_id.replace("_", " ").title()
        roles.append(Role(roleId=role_id, name=role_name, notes=None))
        voice_to_role_id[voice_id] = role_id

    # Determine defaultVoiceId (prefer narrator_male, else first voice)
    if "narrator_male" in seen_voices:
        default_voice_id = "narrator_male"
    else:
        default_voice_id = voice_list[0]

    # Create casting map: roleId -> voiceId (since old format directly uses voice_id)
    casting: dict[str, str] = {}
    for voice_id, role_id in voice_to_role_id.items():
        casting[str(role_id)] = voice_id

    # Create story lines
    story_lines: list[StoryLine] = []
    for line_id, (voice_id, _language, text) in enumerate(lines_data):
        role_id = voice_to_role_id[voice_id]
        story_lines.append(
            StoryLine(
                id=line_id,
                roleId=role_id,
                line=text,
                extra=None,  # Old format doesn't have performance hints
                actorId=None,  # Old format doesn't have per-line overrides
            )
        )

    # Generate title from filename
    title = txt_path.stem.replace("_", " ").title()

    # Determine language: use most common language from lines, or default to "English"
    from collections import Counter

    languages = [_language for _, _language, _ in lines_data]
    language_counts = Counter(languages)
    story_language = language_counts.most_common(1)[0][0] if language_counts else "English"

    return StoryTemplate(
        schemaVersion=1,
        title=title,
        language=story_language,
        defaultVoiceId=default_voice_id,
        roles=roles,
        casting=casting,
        lines=story_lines,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert old .txt story format to JSON template format"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input .txt file path",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output JSON file path (default: stories/<input_stem>.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate but don't write output file",
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1

    try:
        story = parse_txt_story(args.input)
    except ValueError as e:
        print(f"Error parsing file: {e}")
        return 1

    # Validate the story
    errors = validate_story(story.model_dump())
    if errors:
        print("Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return 1

    if args.dry_run:
        print("✓ Story parsed and validated successfully")
        print(f"  Title: {story.title}")
        print(f"  Roles: {len(story.roles)}")
        print(f"  Lines: {len(story.lines)}")
        print(f"  Default voice: {story.defaultVoiceId}")
        return 0

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        stories_dir = get_stories_dir()
        stories_dir.mkdir(parents=True, exist_ok=True)
        output_path = stories_dir / f"{args.input.stem}.json"

    # Write JSON file
    output_path.write_text(json.dumps(story.model_dump(), indent=2, ensure_ascii=False) + "\n")
    print(f"✓ Converted {args.input} -> {output_path}")
    print(f"  Title: {story.title}")
    print(f"  Roles: {len(story.roles)} ({', '.join(r.name for r in story.roles)})")
    print(f"  Lines: {len(story.lines)}")
    print(f"  Default voice: {story.defaultVoiceId}")

    return 0


if __name__ == "__main__":
    exit(main())
