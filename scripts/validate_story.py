#!/usr/bin/env python3
"""Validate a story template JSON file."""

import argparse
import json
import sys

from lib.validation import validate_story


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a story template JSON file.")
    parser.add_argument("path", help="Path to story template JSON")
    args = parser.parse_args()

    try:
        with open(args.path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {args.path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        return 1

    errors = validate_story(data)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
