"""Validation logic for story templates.

This is the raw-JSON validator used by the ``validate_story`` CLI: it turns a
parsed JSON dict into a flat list of human-readable error messages, including
semantic checks (e.g. ``line.roleId`` must reference a defined role) that the
Pydantic models don't perform. The API layer validates via the Pydantic
``StoryTemplate`` model in ``lib.models``; as a final guard this validator also
cross-checks that a structurally valid template constructs that model, so the
CLI can't accept something the API would reject.
"""

from typing import Any


def _is_int(v: Any) -> bool:
    """Check if value is an integer (not bool)."""
    return isinstance(v, int) and not isinstance(v, bool)


def validate_story(data: dict[str, Any]) -> list[str]:
    """
    Validate a story template dictionary.

    Returns a list of error messages. Empty list means valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Story must be a JSON object"]

    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("title must be a non-empty string")

    default_voice = data.get("defaultVoiceId")
    if not isinstance(default_voice, str) or not default_voice.strip():
        errors.append("defaultVoiceId must be a non-empty string")

    roles = data.get("roles")
    if not isinstance(roles, list) or not roles:
        errors.append("roles must be a non-empty array")
        roles = []

    role_ids: set[int] = set()
    for idx, role in enumerate(roles):
        if not isinstance(role, dict):
            errors.append(f"roles[{idx}] must be an object")
            continue
        role_id = role.get("roleId")
        name = role.get("name")
        if not _is_int(role_id) or role_id is None or role_id < 0:
            errors.append(f"roles[{idx}].roleId must be a non-negative integer")
        elif role_id in role_ids:
            errors.append(f"roles[{idx}].roleId {role_id} is duplicated")
        else:
            assert role_id is not None  # Type guard
            role_ids.add(role_id)
        if not isinstance(name, str) or not name.strip():
            errors.append(f"roles[{idx}].name must be a non-empty string")

    casting = data.get("casting", {})
    if casting is not None:
        if not isinstance(casting, dict):
            errors.append("casting must be an object when provided")
        else:
            for k, v in casting.items():
                if not isinstance(k, str) or not k.isdigit():
                    errors.append(f"casting key '{k}' must be a numeric string")
                if not isinstance(v, str) or not v.strip():
                    errors.append(f"casting['{k}'] must be a non-empty string")

    lines = data.get("lines")
    if not isinstance(lines, list) or not lines:
        errors.append("lines must be a non-empty array")
        lines = []

    line_ids: set[int] = set()
    for idx, line in enumerate(lines):
        if not isinstance(line, dict):
            errors.append(f"lines[{idx}] must be an object")
            continue
        line_id = line.get("id")
        role_id = line.get("roleId")
        text = line.get("line")
        if not _is_int(line_id) or line_id is None or line_id < 0:
            errors.append(f"lines[{idx}].id must be a non-negative integer")
        elif line_id in line_ids:
            errors.append(f"lines[{idx}].id {line_id} is duplicated")
        else:
            assert line_id is not None  # Type guard
            line_ids.add(line_id)
        if not _is_int(role_id) or role_id is None or role_id < 0:
            errors.append(f"lines[{idx}].roleId must be a non-negative integer")
        elif role_id not in role_ids:
            errors.append(f"lines[{idx}].roleId {role_id} is not defined in roles")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"lines[{idx}].line must be a non-empty string")

        extra = line.get("extra")
        if extra is not None and not isinstance(extra, str):
            errors.append(f"lines[{idx}].extra must be a string when provided")

        actor_id = line.get("actorId")
        if actor_id is not None and (not isinstance(actor_id, str) or not actor_id.strip()):
            errors.append(f"lines[{idx}].actorId must be a non-empty string when provided")

    # Final guard: a structurally valid template must also construct the
    # Pydantic model the API uses, so the CLI can't accept something the API
    # would reject. Only run when the cheaper checks above already passed.
    if not errors:
        from pydantic import ValidationError

        from lib.models import StoryTemplate

        try:
            StoryTemplate(**data)
        except ValidationError as exc:
            errors.extend(
                f"model: {'.'.join(map(str, err['loc']))}: {err['msg']}" for err in exc.errors()
            )

    return errors
