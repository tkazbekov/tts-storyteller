"""Handle loading the project .env file when running CLI/API code."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_env_loaded = False


def load_env() -> None:
    """Load the repository .env file into the environment (idempotent)."""
    global _env_loaded
    if _env_loaded:
        return

    project_root = Path(__file__).resolve().parents[1]
    dotenv_path = project_root / ".env"

    load_dotenv(dotenv_path=dotenv_path, override=False)
    _env_loaded = True
