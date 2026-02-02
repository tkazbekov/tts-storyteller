#!/usr/bin/env python3
"""
Migration script to transfer file-based data to Postgres database.

Migrates:
- stories/*.json → stories + story_roles + story_lines tables
- voices/voices.json → voices table
- voices/pools.json → voice_pools + voice_pool_members tables
- outputs/story/*/.generation_metadata.json → story_generation_metadata table

Usage:
    DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname python -m scripts.migrate_to_db

Options:
    --dry-run    Show what would be migrated without making changes
    --verbose    Show detailed output during migration
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

from lib.database import close_database, get_database_url, get_session, init_database
from lib.db_models import (
    StoryGenerationMetadataModel,
    StoryLineModel,
    StoryModel,
    StoryRoleModel,
    VoiceModel,
    VoicePoolMemberModel,
    VoicePoolModel,
)
from lib.env import load_env
from lib.paths import (
    get_pools_config_path,
    get_stories_dir,
    get_story_output_dir,
    get_voices_config_path,
)
from lib.storage import list_stories, load_story

load_env()


async def migrate_stories(dry_run: bool = False, verbose: bool = False) -> int:
    """Migrate stories from JSON files to database."""
    stories_dir = get_stories_dir()
    if not stories_dir.exists():
        print("  No stories directory found")
        return 0

    story_ids = list_stories()
    if not story_ids:
        print("  No stories found")
        return 0

    migrated = 0
    for story_id in story_ids:
        try:
            story = load_story(story_id)

            if verbose:
                print(f"  - {story_id}: {story.title}")

            if not dry_run:
                async with get_session() as session:
                    # Check if story already exists
                    from sqlalchemy import select

                    existing = await session.execute(
                        select(StoryModel).where(StoryModel.slug == story_id)
                    )
                    if existing.scalar_one_or_none():
                        if verbose:
                            print("    (skipped - already exists)")
                        continue

                    # Create story
                    story_uuid = uuid.uuid4()
                    story_model = StoryModel(
                        id=story_uuid,
                        slug=story_id,
                        title=story.title,
                        language=story.language,
                        default_voice_id=story.defaultVoiceId,
                        casting=story.casting,
                    )
                    session.add(story_model)

                    # Add roles
                    for role in story.roles:
                        role_model = StoryRoleModel(
                            story_id=story_uuid,
                            role_id=role.roleId,
                            name=role.name,
                            notes=role.notes,
                        )
                        session.add(role_model)

                    # Add lines
                    for idx, line in enumerate(story.lines):
                        line_model = StoryLineModel(
                            story_id=story_uuid,
                            line_index=idx,
                            role_id=line.roleId,
                            line_text=line.line,
                            extra=line.extra,
                            actor_id=line.actorId,
                        )
                        session.add(line_model)

            migrated += 1

        except Exception as e:
            print(f"  ERROR: Failed to migrate story '{story_id}': {e}")

    return migrated


async def migrate_voices(dry_run: bool = False, verbose: bool = False) -> int:
    """Migrate voices from voices.json to database."""
    voices_path = get_voices_config_path()
    if not voices_path.exists():
        print("  No voices.json found")
        return 0

    with open(voices_path) as f:
        voices = json.load(f)

    if not voices:
        print("  No voices found")
        return 0

    migrated = 0
    for voice_data in voices:
        voice_id = voice_data.get("id")
        if not voice_id:
            continue

        if verbose:
            print(f"  - {voice_id}")

        if not dry_run:
            async with get_session() as session:
                # Check if voice already exists
                from sqlalchemy import select

                existing = await session.execute(
                    select(VoiceModel).where(VoiceModel.id == voice_id)
                )
                if existing.scalar_one_or_none():
                    if verbose:
                        print("    (skipped - already exists)")
                    continue

                # Create voice
                voice_model = VoiceModel(
                    id=voice_id,
                    language=voice_data.get("language", "English"),
                    instruction=voice_data.get("instruction", ""),
                    sample_text=voice_data.get("sample_text"),
                )
                session.add(voice_model)

        migrated += 1

    return migrated


async def migrate_pools(dry_run: bool = False, verbose: bool = False) -> int:
    """Migrate pools from pools.json to database."""
    pools_path = get_pools_config_path()
    if not pools_path.exists():
        print("  No pools.json found")
        return 0

    with open(pools_path) as f:
        pools = json.load(f)

    if not pools:
        print("  No pools found")
        return 0

    migrated = 0
    for pool_name, voice_ids in pools.items():
        if verbose:
            print(f"  - {pool_name}: {len(voice_ids)} voices")

        if not dry_run:
            async with get_session() as session:
                # Check if pool already exists
                from sqlalchemy import select

                existing = await session.execute(
                    select(VoicePoolModel).where(VoicePoolModel.name == pool_name)
                )
                if existing.scalar_one_or_none():
                    if verbose:
                        print("    (skipped - already exists)")
                    continue

                # Create pool
                pool_model = VoicePoolModel(name=pool_name)
                session.add(pool_model)
                await session.flush()  # Get pool.id

                # Add members (only for voices that exist in the database)
                for voice_id in voice_ids:
                    # Check if voice exists
                    voice_exists = await session.execute(
                        select(VoiceModel).where(VoiceModel.id == voice_id)
                    )
                    if voice_exists.scalar_one_or_none():
                        member = VoicePoolMemberModel(pool_id=pool_model.id, voice_id=voice_id)
                        session.add(member)

        migrated += 1

    return migrated


async def migrate_metadata(dry_run: bool = False, verbose: bool = False) -> int:
    """Migrate generation metadata from files to database."""
    story_ids = list_stories()
    if not story_ids:
        return 0

    migrated = 0
    for story_id in story_ids:
        output_dir = get_story_output_dir(story_id)
        metadata_path = output_dir / ".generation_metadata.json"

        if not metadata_path.exists():
            continue

        try:
            with open(metadata_path) as f:
                metadata = json.load(f)

            line_hashes = metadata.get("line_hashes")
            language = metadata.get("language", "English")

            if not line_hashes:
                continue

            if verbose:
                print(f"  - {story_id}: {len(line_hashes)} line hashes")

            if not dry_run:
                async with get_session() as session:
                    # Get story UUID
                    from sqlalchemy import select

                    story_result = await session.execute(
                        select(StoryModel).where(StoryModel.slug == story_id)
                    )
                    story_model = story_result.scalar_one_or_none()

                    if not story_model:
                        if verbose:
                            print("    (skipped - story not in database)")
                        continue

                    # Check if metadata already exists
                    existing = await session.execute(
                        select(StoryGenerationMetadataModel).where(
                            StoryGenerationMetadataModel.story_id == story_model.id
                        )
                    )
                    if existing.scalar_one_or_none():
                        if verbose:
                            print("    (skipped - already exists)")
                        continue

                    # Create metadata
                    metadata_model = StoryGenerationMetadataModel(
                        story_id=story_model.id,
                        line_hashes=line_hashes,
                        language=language,
                    )
                    session.add(metadata_model)

            migrated += 1

        except Exception as e:
            print(f"  ERROR: Failed to migrate metadata for '{story_id}': {e}")

    return migrated


async def run_migration(dry_run: bool = False, verbose: bool = False) -> None:
    """Run the full migration."""
    db_url = get_database_url()
    if not db_url:
        print("ERROR: DATABASE_URL environment variable is required")
        sys.exit(1)

    print(f"Database: {db_url.split('@')[1] if '@' in db_url else db_url}")
    print()

    if dry_run:
        print("=== DRY RUN - No changes will be made ===")
        print()

    # Initialize database
    await init_database()

    try:
        # Migrate stories
        print("Migrating stories...")
        stories_count = await migrate_stories(dry_run, verbose)
        print(f"  Migrated {stories_count} stories")
        print()

        # Migrate voices
        print("Migrating voices...")
        voices_count = await migrate_voices(dry_run, verbose)
        print(f"  Migrated {voices_count} voices")
        print()

        # Migrate pools
        print("Migrating pools...")
        pools_count = await migrate_pools(dry_run, verbose)
        print(f"  Migrated {pools_count} pools")
        print()

        # Migrate metadata
        print("Migrating generation metadata...")
        metadata_count = await migrate_metadata(dry_run, verbose)
        print(f"  Migrated {metadata_count} metadata entries")
        print()

        print("=== Migration complete ===")
        print(
            f"Total: {stories_count} stories, {voices_count} voices, "
            f"{pools_count} pools, {metadata_count} metadata entries"
        )

    finally:
        await close_database()


def main():
    parser = argparse.ArgumentParser(description="Migrate file-based data to Postgres database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")

    args = parser.parse_args()

    asyncio.run(run_migration(dry_run=args.dry_run, verbose=args.verbose))


if __name__ == "__main__":
    main()
