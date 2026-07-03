"""Offline migration-chain checks (no database required)."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_migration_chain_is_unbroken():
    """Regression: every migration's down_revision must name a real revision,
    and the chain must have exactly one head."""
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    script = ScriptDirectory.from_config(cfg)

    heads = script.get_heads()
    assert len(heads) == 1

    # walk_revisions raises if any down_revision points at a missing revision.
    revisions = list(script.walk_revisions("base", "heads"))
    assert len(revisions) >= 3
