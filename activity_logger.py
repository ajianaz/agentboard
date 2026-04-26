"""activity_logger.py - Auto-logging middleware for AgentBoard API operations.

Intercepts all write operations (POST, PATCH, DELETE) and records them to the
activity log automatically. Supports noise filtering and actor extraction.

Usage:
    from activity_logger import log_activity_event
    # Called by API router after successful write operations
    log_activity_event("task", task_id, "create", actor, detail)
"""

import json
from db import get_db, gen_id

# Actions to skip (noise filtering)
_SKIP_ACTIONS = frozenset({
    "health_check",
    "static_serve",
    "options",
})

# Target types that get logged
_LOGGED_TARGETS = frozenset({
    "task", "page", "project", "comment", "agent",
    "discussion", "api_key", "settings",
})


def log_activity_event(
    target_type: str,
    target_id: str,
    action: str,
    actor: str,
    detail: dict | None = None,
    project_id: str | None = None,
) -> str | None:
    """Log an activity event to the activity table.

    Args:
        target_type: Type of target (task, page, project, comment, etc.)
        target_id: ID of the target object
        action: Action performed (create, update, delete, etc.)
        actor: Who performed the action (agent ID or 'owner')
        detail: Optional structured detail dict (before/after values, etc.)
        project_id: Optional project ID for project-scoped activity

    Returns:
        Activity ID if logged, None if skipped (noise filtered).
    """
    # Noise filtering
    if action.lower() in _SKIP_ACTIONS:
        return None
    if target_type.lower() not in _LOGGED_TARGETS:
        return None

    try:
        conn = get_db()
        activity_id = gen_id()
        detail_json = json.dumps(detail or {}, ensure_ascii=False, default=str)
        conn.execute(
            """INSERT INTO activity (id, project_id, target_type, target_id, action, actor, detail, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (activity_id, project_id, target_type, target_id, action, actor, detail_json),
        )
        conn.commit()
        conn.close()
        return activity_id
    except Exception:
        # Never let logging failures break the main operation
        return None


def log_task_event(task_id: str, action: str, actor: str, detail: dict | None = None, project_id: str | None = None) -> str | None:
    """Convenience function for task-related activity logging."""
    return log_activity_event("task", task_id, action, actor, detail, project_id)


def log_project_event(project_id: str, action: str, actor: str, detail: dict | None = None) -> str | None:
    """Convenience function for project-related activity logging."""
    return log_activity_event("project", project_id, action, actor, detail, project_id)


def log_comment_event(comment_id: str, action: str, actor: str, detail: dict | None = None, project_id: str | None = None) -> str | None:
    """Convenience function for comment-related activity logging."""
    return log_activity_event("comment", comment_id, action, actor, detail, project_id)


def log_page_event(page_id: str, action: str, actor: str, detail: dict | None = None, project_id: str | None = None) -> str | None:
    """Convenience function for page-related activity logging."""
    return log_activity_event("page", page_id, action, actor, detail, project_id)


def get_actor_from_headers(headers: dict) -> str:
    """Extract actor name from request headers.

    Checks X-Actor header first, falls back to 'owner'.
    """
    actor = headers.get("x-actor", "")
    return actor.strip() if actor else "owner"
