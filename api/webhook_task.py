"""api/webhook_task.py — Webhook endpoint for agent task-status updates.

Agents POST here to update task status in real-time without full API access.

Endpoint:
    POST /api/webhook/task-update — update task status + log activity

Auth: Bearer token (any valid AgentBoard key)
Rate limit: 60 requests/minute per agent (in-memory)

Payload:
    {
        "agent": "cto",              // agent name (for activity log)
        "task_ref": "I-025",         // task title prefix to match
        "status": "in_progress",     // new status (todo|proposed|in_progress|review|done)
        "detail": "Working on..."    // optional detail for activity log
    }
"""

import json
import time
from db import get_db
from api import router

# ── Simple in-memory rate limiter ──────────────────────────────────────
_rate_limits: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 60     # requests per window


def _check_rate_limit(agent: str) -> bool:
    """Check if agent is within rate limit. Returns True if allowed."""
    now = time.time()
    if agent not in _rate_limits:
        _rate_limits[agent] = []
    # Clean old entries
    _rate_limits[agent] = [t for t in _rate_limits[agent] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limits[agent]) >= RATE_LIMIT_MAX:
        return False
    _rate_limits[agent].append(now)
    return True


VALID_STATUSES = {"todo", "proposed", "in_progress", "review", "done"}


@router.post("/api/webhook/task-update")
def webhook_task_update(params, query, body, headers):
    """Receive task status update from an agent."""
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, TypeError):
        return 400, {"error": "Invalid JSON body", "code": "BAD_REQUEST"}

    # Validate required fields
    agent = str(data.get("agent", "")).strip()
    task_ref = str(data.get("task_ref", "")).strip()
    new_status = str(data.get("status", "")).strip().lower()
    detail = str(data.get("detail", "")).strip()

    if not agent:
        return 400, {"error": "agent is required", "code": "VALIDATION_ERROR"}
    if not task_ref:
        return 400, {"error": "task_ref is required", "code": "VALIDATION_ERROR"}
    if new_status not in VALID_STATUSES:
        return 400, {"error": f"status must be one of: {', '.join(sorted(VALID_STATUSES))}", "code": "VALIDATION_ERROR"}

    # Rate limit
    if not _check_rate_limit(agent):
        return 429, {"error": "Rate limit exceeded (60/min)", "code": "RATE_LIMITED"}

    conn = get_db()

    # Find task by title containing the ref (fuzzy match on prefix)
    row = conn.execute(
        "SELECT id, project_id, title, status FROM tasks WHERE title LIKE ? LIMIT 1",
        (f"{task_ref}%",),
    ).fetchone()

    if not row:
        conn.close()
        return 404, {"error": f"Task matching '{task_ref}' not found", "code": "NOT_FOUND"}

    task_id = row["id"]
    project_id = row["project_id"]
    old_status = row["status"]

    if old_status == new_status:
        conn.close()
        return 200, {"message": "Status unchanged", "task_id": task_id, "status": new_status}

    # Update task status
    if new_status == "done":
        conn.execute(
            "UPDATE tasks SET status = ?, completed_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (new_status, task_id),
        )
    elif new_status == "in_progress":
        conn.execute(
            "UPDATE tasks SET status = ?, started_at = COALESCE(started_at, datetime('now')), updated_at = datetime('now') WHERE id = ?",
            (new_status, task_id),
        )
    else:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, task_id),
        )

    # Log activity
    activity_detail = {"old_status": old_status, "new_status": new_status}
    if detail:
        activity_detail["detail"] = detail
    conn.execute(
        """INSERT INTO activity (id, project_id, target_type, target_id, action, actor, detail, created_at)
           VALUES (lower(hex(randomblob(8))), ?, 'task', ?, 'status_change', ?, ?, datetime('now'))""",
        (project_id, task_id, agent, json.dumps(activity_detail)),
    )

    conn.commit()

    # Fetch updated task
    updated = conn.execute("SELECT id, title, status FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()

    return 200, {
        "message": "Task updated",
        "task_id": task_id,
        "task_title": updated["title"],
        "old_status": old_status,
        "new_status": new_status,
    }
