"""Reusable input validation helpers for AgentBoard API endpoints.

Provides enum validation, length limits, and sanitization utilities
to ensure consistent input handling across all endpoints.
"""

from typing import Any

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

VALID_VISIBILITIES = frozenset({"public", "hidden"})

VALID_DISCUSSION_STATUSES = frozenset({"open", "closed", "consensus"})

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
