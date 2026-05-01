"""api/webhook_task.py — Webhook endpoints for agent integration.

Endpoints:
    POST /api/webhook/task-update  — update existing task status + log activity
    POST /api/webhook/agent-event  — auto-track agent lifecycle (create/update tasks)

Auth: Bearer token (any valid AgentBoard key)
Rate limit: 60 requests/minute per agent (in-memory)

--- task-update payload ---
{
    "agent": "cto",              // agent name (for activity log)
    "task_ref": "I-025",         // task title prefix to match
    "status": "in_progress",     // new status (todo|proposed|in_progress|review|done)
    "detail": "Working on..."    // optional detail for activity log
}

--- agent-event payload ---
{
    "agent_id": "zeko",              // unique agent identifier
    "event_type": "session_start",   // session_start|session_end|task_start|task_end
    "session_id": "abc123",          // session identifier (for dedup + grouping)
    "message": "Fix the login bug",  // first message or summary (for task title)
    "metadata": {}                   // optional, freeform
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


# ── Agent Event Endpoint ────────────────────────────────────────────

VALID_AGENT_EVENTS = {"session_start", "session_end", "task_start", "task_end"}


def _get_agent_project_mapping() -> dict[str, str]:
    """Get agent → project slug mapping from config.

    Returns mapping like {"zeko": "infrastructure", "cto": "agentboard", ...}.
    Falls back to a default project if no mapping exists for the agent.
    """
    try:
        from config import get_config
        cfg = get_config()
        return cfg.get("agents", {})
    except Exception:
        return {}


def _get_or_create_default_project(conn, agent_id: str) -> str | None:
    """Get project_id for an agent, creating a default project if needed."""
    mapping = _get_agent_project_mapping()
    project_slug = mapping.get(agent_id)

    if project_slug:
        row = conn.execute(
            "SELECT id FROM projects WHERE slug = ? AND is_archived = 0",
            (project_slug,),
        ).fetchone()
        if row:
            return row["id"]

    # No mapping or project not found — create a default "Agent Tasks" project
    default_slug = "agent-tasks"
    row = conn.execute(
        "SELECT id FROM projects WHERE slug = ? AND is_archived = 0",
        (default_slug,),
    ).fetchone()
    if row:
        return row["id"]

    # Create the default project
    from config import get_config
    cfg = get_config()
    statuses = cfg.get("auth", {}).get("statuses", cfg.get("features", {}).get("statuses", [
        {"key": "proposed", "label": "Proposed", "color": "#f59e0b"},
        {"key": "todo", "label": "To Do", "color": "#6b7280"},
        {"key": "in_progress", "label": "In Progress", "color": "#3b82f6"},
        {"key": "review", "label": "Review", "color": "#8b5cf6"},
        {"key": "done", "label": "Done", "color": "#22c55e"},
    ]))
    priorities = cfg.get("auth", {}).get("priorities", cfg.get("features", {}).get("priorities", [
        {"key": "critical", "label": "Critical", "color": "#ef4444"},
        {"key": "high", "label": "High", "color": "#f97316"},
        {"key": "medium", "label": "Medium", "color": "#eab308"},
        {"key": "low", "label": "Low", "color": "#22c55e"},
        {"key": "none", "label": "None", "color": "#6b7280"},
    ]))

    project_id = conn.execute(
        """INSERT INTO projects (id, name, slug, description, icon, color, position,
           statuses, priorities, tags, is_archived, metadata, created_by, created_at, updated_at)
           VALUES (lower(hex(randomblob(8))), 'Agent Tasks', 'agent-tasks',
                   'Auto-tracked tasks from AI agents', '🤖', '#6366f1', 1,
                   ?, ?, '[]', 0, '{}', ?, datetime('now'), datetime('now'))""",
        (json.dumps(statuses), json.dumps(priorities), agent_id),
    ).lastrowid
    conn.commit()
    return project_id


@router.post("/api/webhook/agent-event")
def webhook_agent_event(params, query, body, headers):
    """Receive agent lifecycle event — auto-create or update tasks.

    This is the primary auto-tracking endpoint. Any agent framework can POST
    structured lifecycle events here and AgentBoard will automatically manage tasks.

    Event types:
        session_start — agent begins processing a user session → auto-create task
        session_end   — agent finishes a session → mark task as done
        task_start    — agent starts a specific task → create/update task
        task_end      — agent finishes a task → mark as done

    Dedup: uses session_id to prevent duplicate task creation. If a task with
    the same session_id already exists, it updates instead of creating new.
    """
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, TypeError):
        return 400, {"error": "Invalid JSON body", "code": "BAD_REQUEST"}

    # Validate required fields
    agent_id = str(data.get("agent_id", "")).strip().lower()
    event_type = str(data.get("event_type", "")).strip().lower()
    session_id = str(data.get("session_id", "")).strip()
    message = str(data.get("message", "")).strip()

    if not agent_id:
        return 400, {"error": "agent_id is required", "code": "VALIDATION_ERROR"}
    if event_type not in VALID_AGENT_EVENTS:
        return 400, {
            "error": f"event_type must be one of: {', '.join(sorted(VALID_AGENT_EVENTS))}",
            "code": "VALIDATION_ERROR",
        }

    # Skip cron sessions
    if session_id.startswith("cron_"):
        return 200, {"message": "Ignored (cron session)", "skipped": True}

    # Rate limit
    if not _check_rate_limit(agent_id):
        return 429, {"error": "Rate limit exceeded (60/min)", "code": "RATE_LIMITED"}

    conn = get_db()

    # Get or create project for this agent
    project_id = _get_or_create_default_project(conn, agent_id)
    if not project_id:
        conn.close()
        return 500, {"error": "Failed to get/create project", "code": "INTERNAL_ERROR"}

    result = {"agent_id": agent_id, "event_type": event_type}

    if event_type in ("session_start", "task_start"):
        # Build task title from session_id + message preview
        if session_id and message:
            # Truncate message for title
            msg_preview = message[:80].replace("\n", " ")
            title = f"[{session_id[:12]}] {msg_preview}"
        elif message:
            title = message[:100].replace("\n", " ")
        elif session_id:
            title = f"[{session_id[:12]}] Agent session"
        else:
            title = f"Agent task ({agent_id})"

        # Dedup: check if task with this session_id already exists
        existing = None
        if session_id:
            existing = conn.execute(
                "SELECT id, status FROM tasks WHERE description LIKE ? AND project_id = ? LIMIT 1",
                (f'%session_id={session_id}%', project_id),
            ).fetchone()

        if existing:
            # Update existing task to in_progress
            task_id = existing["id"]
            if existing["status"] != "in_progress":
                conn.execute(
                    """UPDATE tasks SET status = 'in_progress',
                       started_at = COALESCE(started_at, datetime('now')),
                       updated_at = datetime('now')
                       WHERE id = ?""",
                    (task_id,),
                )
            result["action"] = "updated"
            result["task_id"] = task_id
        else:
            # Create new task
            task_id = conn.execute(
                """INSERT INTO tasks (id, project_id, title, description, status, priority,
                   assignee, tags, position, metadata, created_by, created_at, updated_at)
                   VALUES (lower(hex(randomblob(8))), ?, ?, ?, 'in_progress', 'medium',
                   ?, '["auto-tracked"]', 1.0, ?, ?, datetime('now'), datetime('now'))""",
                (
                    project_id,
                    title,
                    f"Auto-tracked from agent event.\nagent_id={agent_id}\nevent_type={event_type}\nsession_id={session_id}",
                    agent_id,
                    json.dumps({
                        "session_id": session_id,
                        "auto_tracked": True,
                        "event_type": event_type,
                    }),
                    agent_id,
                ),
            ).lastrowid
            result["action"] = "created"
            result["task_id"] = task_id

        # Log activity
        conn.execute(
            """INSERT INTO activity (id, project_id, target_type, target_id, action, actor, detail, created_at)
               VALUES (lower(hex(randomblob(8))), ?, 'task', ?, 'auto_created', ?, ?, datetime('now'))""",
            (project_id, task_id, agent_id, json.dumps({
                "event_type": event_type,
                "session_id": session_id,
                "title": title,
            })),
        )

    elif event_type in ("session_end", "task_end"):
        # Find existing task by session_id and mark as done
        task_id = None
        if session_id:
            row = conn.execute(
                "SELECT id, status FROM tasks WHERE description LIKE ? AND project_id = ? LIMIT 1",
                (f'%session_id={session_id}%', project_id),
            ).fetchone()
            if row:
                task_id = row["id"]

        if task_id:
            old_status = conn.execute(
                "SELECT status FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()["status"]

            if old_status != "done":
                conn.execute(
                    """UPDATE tasks SET status = 'done',
                       completed_at = datetime('now'), updated_at = datetime('now')
                       WHERE id = ?""",
                    (task_id,),
                )
                result["action"] = "completed"
                result["task_id"] = task_id

                # Log activity
                conn.execute(
                    """INSERT INTO activity (id, project_id, target_type, target_id, action, actor, detail, created_at)
                       VALUES (lower(hex(randomblob(8))), ?, 'task', ?, 'auto_completed', ?, ?, datetime('now'))""",
                    (project_id, task_id, agent_id, json.dumps({
                        "event_type": event_type,
                        "session_id": session_id,
                        "old_status": old_status,
                    })),
                )
            else:
                result["action"] = "unchanged"
                result["task_id"] = task_id
        else:
            result["action"] = "no_matching_task"
            result["detail"] = f"No task found for session_id={session_id}"

    conn.commit()
    conn.close()

    return 200, result
