"""Reusable input validation helpers for AgentBoard API endpoints.

Provides enum validation, length limits, and sanitization utilities
to ensure consistent input handling across all endpoints.
"""

from typing import Any
import json

# ---------------------------------------------------------------------------
# Valid enum sets — match the system's actual values (not arbitrary subsets)
# ---------------------------------------------------------------------------

VALID_STATUSES = frozenset({
    "todo", "proposed", "in_progress", "review", "done",
    "rejected", "repurposed",
})

VALID_PRIORITIES = frozenset({
    "none", "low", "medium", "high", "critical",
})

VALID_TASK_TYPES = frozenset({
    # Engineering
    "milestone", "feature", "task", "bugfix", "chore", "refactor",
    # Design & Content
    "design", "content", "copywriting", "review",
    # Marketing & Sales
    "campaign", "outreach", "analytics",
    # Operations & Planning
    "planning", "operations", "research", "meeting",
    # Hierarchy (v0.7)
    "mission", "slice",
})

MAX_TYPE_LENGTH = 30

VALID_VISIBILITIES = frozenset({"public", "hidden"})

VALID_DISCUSSION_STATUSES = frozenset({"open", "closed", "consensus"})

VALID_PLAN_STATUSES = frozenset({
    "proposed", "approved", "executing", "done", "rejected",
})

VALID_VERDICTS = frozenset({"approve", "conditional", "reject", ""})

# ---------------------------------------------------------------------------
# Length limits
# ---------------------------------------------------------------------------

MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 10000
MAX_COMMENT_LENGTH = 10000
MAX_NAME_LENGTH = 200
MAX_SLUG_LENGTH = 60
MAX_CONTENT_LENGTH = 500000  # pages can be large markdown documents

MAX_STEPS_LENGTH = 50000  # plans steps JSON array can be large
MAX_CONTEXT_LENGTH = 50000  # plan context/background text


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_enum(value: Any, valid_set: frozenset, default: str | None = None) -> str | None:
    """Validate that *value* is a member of *valid_set* after stripping.

    Returns the stripped value if valid, *default* otherwise.
    """
    if not value or not isinstance(value, str):
        return default
    stripped = value.strip()
    if stripped in valid_set:
        return stripped
    return default


def validate_length(value: str, max_len: int, field_name: str = "field") -> tuple[bool, str]:
    """Validate string length. Returns (is_valid, error_message_or_empty).

    Always returns the truncated-safe string as the second element on success.
    """
    if len(value) > max_len:
        return False, f"{field_name} exceeds maximum length of {max_len} characters (got {len(value)})"
    return True, ""


def sanitize_string(value: Any, max_len: int | None = None) -> str:
    """Strip whitespace from a value, optionally enforce max length.

    Returns empty string for None / non-string input.
    """
    if not value or not isinstance(value, str):
        return ""
    result = value.strip()
    if max_len is not None and len(result) > max_len:
        result = result[:max_len]
    return result


def validate_title(value: Any, max_len: int = MAX_TITLE_LENGTH, field_name: str = "title") -> tuple[str | None, str | None]:
    """Validate a title field: must be non-empty string within length limit.

    Returns (sanitized_value, error_message).
    On success error_message is None; on failure sanitized_value is None.
    """
    if not value or not isinstance(value, str):
        return None, f"{field_name} is required"
    title = value.strip()
    if not title:
        return None, f"{field_name} is required"
    if len(title) > max_len:
        return None, f"{field_name} exceeds maximum length of {max_len} characters (got {len(title)})"
    return title, None


def validate_task_type(value: Any, default: str = "task") -> tuple[str, str | None]:
    """Validate task type: accepts any preset type OR a well-formatted custom type.

    Preset types (VALID_TASK_TYPES) are the curated list. Custom types are
    accepted if they match: lowercase alphanumeric, hyphens, underscores,
    max MAX_TYPE_LENGTH chars, starts with a letter.

    Returns (validated_type, error_message).
    On success error_message is None.
    """
    import re

    if not value or not isinstance(value, str):
        return default, None

    stripped = value.strip().lower()
    if not stripped:
        return default, None

    if len(stripped) > MAX_TYPE_LENGTH:
        return default, f"Task type exceeds max {MAX_TYPE_LENGTH} chars (got {len(stripped)})"

    # Preset types pass immediately
    if stripped in VALID_TASK_TYPES:
        return stripped, None

    # Custom types: must match [a-z][a-z0-9_-]*
    if re.match(r'^[a-z][a-z0-9_-]*$', stripped):
        return stripped, None

    return default, f"Invalid type '{value}': use preset types or custom (lowercase a-z, 0-9, hyphens, underscores)"


def validate_text(value: Any, max_len: int = MAX_DESCRIPTION_LENGTH, field_name: str = "description") -> str:
    """Validate a free-text field: strip whitespace and enforce max length.

    Returns the sanitized string (truncated if too long). Never fails.
    """
    if not value or not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def validate_steps(value: Any) -> tuple[list, str | None]:
    """Validate plan steps: must be a JSON array of objects with 'title' field.

    Each step should have: {title: str, description?: str, order?: int}
    Returns (validated_steps_list, error_message).
    """
    if value is None:
        return [], None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return [], "Steps must be a valid JSON array"
    if not isinstance(value, list):
        return [], "Steps must be a JSON array"
    if len(value) > 100:
        value = value[:100]
    validated = []
    for i, step in enumerate(value):
        if not isinstance(step, dict):
            return [], f"Step {i+1} must be an object"
        if "title" not in step or not isinstance(step["title"], str) or not step["title"].strip():
            return [], f"Step {i+1} must have a non-empty 'title'"
        validated.append({
            "title": step["title"].strip()[:500],
            "description": step.get("description", "")[:2000] if isinstance(step.get("description"), str) else "",
            "order": step.get("order", i + 1) if isinstance(step.get("order"), int) else (i + 1),
        })
    return validated, None
