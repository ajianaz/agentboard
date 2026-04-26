"""AgentBoard — Task CRUD, HITL transitions, and cross-project queries.

Endpoints:
    GET    /api/projects/{slug}/tasks           — list tasks in project
    POST   /api/projects/{slug}/tasks           — create task
    PATCH  /api/tasks/{id}                      — update task (HITL transitions)
    DELETE /api/tasks/{id}                      — delete task
    GET    /api/tasks?project=all               — cross-project tasks
    GET    /api/tasks/{id}                      — single task with comments
"""

import json
from db import get_db, gen_id
from api import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_body(body: bytes) -> dict:
    """Safely parse JSON body, returning empty dict on empty/invalid input."""
    if not body:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return {}


def _task_row_to_dict(row) -> dict:
    """Convert a task Row to a plain dict with JSON fields parsed."""
    d = dict(row)
    for field in ("tags", "metadata"):
        raw = d.get(field)
        if isinstance(raw, str):
            try:
                d[field] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                d[field] = [] if field == "tags" else {}
    return d


def _log_activity(conn, project_id: str | None, target_type: str,
                  target_id: str | None, action: str, actor: str,
                  detail: dict | None = None):
    """Insert a row into the activity log."""
    conn.execute(
        """INSERT INTO activity (id, project_id, target_type, target_id, action, actor, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (gen_id(), project_id, target_type, target_id, action, actor,
         json.dumps(detail or {})),
    )


def _get_first(query_list, default=""):
    """Extract the first value from a query parameter list, or return default."""
    if query_list and len(query_list) > 0:
        return query_list[0]
    return default


# ---------------------------------------------------------------------------
# HITL Status Transition Map
# ---------------------------------------------------------------------------
# Maps (old_status, new_status) → (activity_action, detail_snippet)
# "any" as old_status means the transition is valid from any state.

HITL_TRANSITIONS = {
    # proposed → todo (owner approves)
    ("proposed", "todo"): ("approved", "Task approved and moved to To Do"),
    # proposed → rejected (owner rejects)
    ("proposed", "rejected"): ("rejected", "Task rejected"),
    # any → in_progress (agent starts work)
    # We use a special key; checked at runtime.
    # any → review (agent submits for review)
    # review → done (owner approves work)
    ("review", "done"): ("approved", "Work approved and completed"),
    # review → in_progress (owner requests changes)
    ("review", "in_progress"): ("changes requested", "Changes requested, sent back to In Progress"),
}

# Transitions that fire from ANY old status
HITL_ANY_TRANSITIONS = {
    "in_progress": ("started", "Work started"),
    "review": ("submitted for review", "Submitted for review"),
    "rejected": ("rejected", "Task rejected"),
}


def _compute_hitl_activity(old_status: str, new_status: str) -> tuple[str, str] | None:
    """Return (action, detail) for a status transition, or None if no HITL activity."""
    # Check specific transition first
    specific = HITL_TRANSITIONS.get((old_status, new_status))
    if specific:
        return specific

    # Check any-from transitions (but only if old != new)
    if old_status != new_status:
        any_trans = HITL_ANY_TRANSITIONS.get(new_status)
        if any_trans:
            return any_trans

    return None


# ---------------------------------------------------------------------------
# GET /api/projects/{slug}/tasks
# ---------------------------------------------------------------------------

@router.get("/api/projects/{slug}/tasks")
def list_project_tasks(params, query, body, headers):
    slug = params["slug"]
    conn = get_db()

    # Resolve project
    project = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not project:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project_id = project["id"]

    # Build query with filters
    conditions = ["t.project_id = ?"]
    sql_params: list = [project_id]

    # Filter by status
    status_filter = _get_first(query.get("status"))
    if status_filter:
        conditions.append("t.status = ?")
        sql_params.append(status_filter)

    # Filter by assignee
    assignee_filter = _get_first(query.get("assignee"))
    if assignee_filter:
        conditions.append("t.assignee = ?")
        sql_params.append(assignee_filter)

    # Filter by priority
    priority_filter = _get_first(query.get("priority"))
    if priority_filter:
        conditions.append("t.priority = ?")
        sql_params.append(priority_filter)

    # Filter by tag (JSON array contains)
    tag_filter = _get_first(query.get("tag"))
    if tag_filter:
        conditions.append("t.tags LIKE ?")
        sql_params.append(f'%"{tag_filter}"%')

    where_clause = " AND ".join(conditions)

    rows = conn.execute(
        f"""SELECT t.* FROM tasks t
            WHERE {where_clause}
            ORDER BY t.status ASC, t.position ASC, t.created_at ASC""",
        sql_params,
    ).fetchall()

    tasks = [_task_row_to_dict(r) for r in rows]
    conn.close()
    return 200, {"tasks": tasks}


# ---------------------------------------------------------------------------
# POST /api/projects/{slug}/tasks
# ---------------------------------------------------------------------------

@router.post("/api/projects/{slug}/tasks")
def create_task(params, query, body, headers):
    slug = params["slug"]
    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    conn = get_db()

    # Resolve project
    project = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not project:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project_id = project["id"]

    # Validate title
    title = (data.get("title") or "").strip()
    if not title:
        conn.close()
        return 400, {"error": "Task title is required", "code": "VALIDATION_ERROR"}

    description = (data.get("description") or "").strip()
    status = (data.get("status") or "todo").strip()
    priority = (data.get("priority") or "none").strip()
    assignee = (data.get("assignee") or "").strip()
    tags = data.get("tags") or []
    due_date = (data.get("due_date") or "").strip() or None

    # Determine position (append to end of status group)
    pos_row = conn.execute(
        "SELECT MAX(position) as max_pos FROM tasks WHERE project_id = ? AND status = ?",
        (project_id, status),
    ).fetchone()
    position = (pos_row["max_pos"] or 0) + 1

    task_id = gen_id()
    created_by = (data.get("created_by") or actor).strip()

    # Handle started_at / completed_at for specific statuses
    started_at = None
    completed_at = None
    if status == "in_progress":
        import datetime
        started_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif status == "done":
        import datetime
        completed_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn.execute(
        """INSERT INTO tasks
           (id, project_id, title, description, status, priority, assignee,
            tags, position, due_date, started_at, completed_at, metadata, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, project_id, title, description, status, priority, assignee,
         json.dumps(tags), position, due_date, started_at, completed_at,
         json.dumps({}), created_by),
    )

    # Log HITL activity for creation
    if status == "proposed":
        _log_activity(conn, project_id, "task", task_id, "proposed", actor,
                      {"title": title, "status": status})
    else:
        _log_activity(conn, project_id, "task", task_id, "created", actor,
                      {"title": title, "status": status})

    conn.commit()

    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    task = _task_row_to_dict(row)
    conn.close()

    return 201, {"task": task}


# ---------------------------------------------------------------------------
# PATCH /api/tasks/{id}
# ---------------------------------------------------------------------------

@router.patch("/api/tasks/{id}")
def update_task(params, query, body, headers):
    task_id = params["id"]
    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    conn = get_db()

    # Fetch existing task
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Task '{task_id}' not found", "code": "NOT_FOUND"}

    old_status = row["status"]
    project_id = row["project_id"]

    updates = {}
    detail_changes = {}

    # Title
    if "title" in data and data["title"] is not None:
        new_title = str(data["title"]).strip()
        if not new_title:
            conn.close()
            return 400, {"error": "Task title cannot be empty", "code": "VALIDATION_ERROR"}
        updates["title"] = new_title
        detail_changes["title"] = new_title

    # Description
    if "description" in data and data["description"] is not None:
        updates["description"] = str(data["description"]).strip()

    # Status — HITL transitions
    if "status" in data and data["status"] is not None:
        new_status = str(data["status"]).strip()
        if new_status != old_status:
            updates["status"] = new_status

            # Set timestamps based on status
            if new_status == "in_progress":
                import datetime
                updates["started_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif new_status == "done":
                import datetime
                updates["completed_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Priority
    if "priority" in data and data["priority"] is not None:
        updates["priority"] = str(data["priority"]).strip()

    # Assignee
    if "assignee" in data and data["assignee"] is not None:
        new_assignee = str(data["assignee"]).strip()
        updates["assignee"] = new_assignee
        if new_assignee != row["assignee"]:
            detail_changes["assignee"] = new_assignee

    # Tags
    if "tags" in data and data["tags"] is not None:
        updates["tags"] = json.dumps(data["tags"])

    # Due date
    if "due_date" in data:
        updates["due_date"] = str(data["due_date"]).strip() or None

    # Position
    if "position" in data and data["position"] is not None:
        try:
            updates["position"] = float(data["position"])
        except (ValueError, TypeError):
            pass

    # Metadata
    if "metadata" in data and data["metadata"] is not None:
        updates["metadata"] = json.dumps(data["metadata"])

    # Build and execute UPDATE
    if not updates:
        # No field updates — but still check for comment
        if "comment" in data and data["comment"]:
            comment_text = str(data["comment"]).strip()
            if comment_text:
                conn.execute(
                    "INSERT INTO comments (id, target_type, target_id, author, content) VALUES (?, ?, ?, ?, ?)",
                    (gen_id(), "task", task_id, actor, comment_text),
                )
                conn.commit()
        conn.close()
        return 200, {"task": _task_row_to_dict(row)}

    set_parts = []
    set_values = []
    for key, val in updates.items():
        set_parts.append(f"{key} = ?")
        set_values.append(val)
    set_values.append(task_id)

    conn.execute(
        f"UPDATE tasks SET {', '.join(set_parts)}, updated_at = datetime('now') WHERE id = ?",
        set_values,
    )

    # Log HITL status transition activity
    new_status = updates.get("status")
    if new_status and new_status != old_status:
        hitl = _compute_hitl_activity(old_status, new_status)
        if hitl:
            action, detail_text = hitl
            _log_activity(conn, project_id, "task", task_id, action, actor,
                          {"title": row["title"], "from": old_status, "to": new_status, "detail": detail_text})
        else:
            # Generic status change log
            _log_activity(conn, project_id, "task", task_id, "status changed", actor,
                          {"title": row["title"], "from": old_status, "to": new_status})
    elif detail_changes:
        # Log field-level updates (but not status since that's handled above)
        _log_activity(conn, project_id, "task", task_id, "updated", actor,
                      {"title": row["title"], **detail_changes})

    # Handle comment field — creates a comment on the task
    if "comment" in data and data["comment"]:
        comment_text = str(data["comment"]).strip()
        if comment_text:
            conn.execute(
                "INSERT INTO comments (id, target_type, target_id, author, content) VALUES (?, ?, ?, ?, ?)",
                (gen_id(), "task", task_id, actor, comment_text),
            )

    conn.commit()

    updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    task = _task_row_to_dict(updated)
    conn.close()

    return 200, {"task": task}


# ---------------------------------------------------------------------------
# DELETE /api/tasks/{id}
# ---------------------------------------------------------------------------

@router.delete("/api/tasks/{id}")
def delete_task(params, query, body, headers):
    task_id = params["id"]
    actor = headers.get("x-actor", "owner")

    conn = get_db()

    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Task '{task_id}' not found", "code": "NOT_FOUND"}

    project_id = row["project_id"]
    task_title = row["title"]

    # Delete comments associated with this task
    conn.execute("DELETE FROM comments WHERE target_type = 'task' AND target_id = ?", (task_id,))

    # Delete the task
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    _log_activity(conn, project_id, "task", task_id, "deleted", actor,
                  {"title": task_title})

    conn.commit()
    conn.close()

    return 200, {"deleted": True, "id": task_id}


# ---------------------------------------------------------------------------
# GET /api/tasks?project=all — cross-project tasks
# ---------------------------------------------------------------------------

@router.get("/api/tasks")
def list_cross_project_tasks(params, query, body, headers):
    project_filter = _get_first(query.get("project"))

    # If no project=all, this endpoint isn't for cross-project queries
    # But we still serve it as a fallback — return tasks from all active projects
    conn = get_db()

    conditions = []
    sql_params: list = []

    # Only join with projects if filtering by project=all (active only)
    # or no project filter at all (also active only)
    if project_filter and project_filter.lower() != "all":
        # Filter by a specific project slug
        conditions.append("p.slug = ?")
        sql_params.append(project_filter)

    # Status filter
    status_filter = _get_first(query.get("status"))
    if status_filter:
        conditions.append("t.status = ?")
        sql_params.append(status_filter)

    # Assignee filter
    assignee_filter = _get_first(query.get("assignee"))
    if assignee_filter:
        conditions.append("t.assignee = ?")
        sql_params.append(assignee_filter)

    # Priority filter
    priority_filter = _get_first(query.get("priority"))
    if priority_filter:
        conditions.append("t.priority = ?")
        sql_params.append(priority_filter)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    rows = conn.execute(
        f"""SELECT t.*, p.name as project_name, p.slug as project_slug
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.is_archived = 0 AND {where_clause}
            ORDER BY t.status ASC, t.position ASC, t.created_at ASC""",
        sql_params,
    ).fetchall()

    tasks = []
    for r in rows:
        task = _task_row_to_dict(r)
        task["project_name"] = r["project_name"]
        task["project_slug"] = r["project_slug"]
        tasks.append(task)

    conn.close()
    return 200, {"tasks": tasks}


# ---------------------------------------------------------------------------
# GET /api/tasks/{id} — single task with comments
# ---------------------------------------------------------------------------

@router.get("/api/tasks/{id}")
def get_task(params, query, body, headers):
    task_id = params["id"]
    conn = get_db()

    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Task '{task_id}' not found", "code": "NOT_FOUND"}

    task = _task_row_to_dict(row)

    # Include project name and slug
    project = conn.execute(
        "SELECT name, slug FROM projects WHERE id = ?", (row["project_id"],)
    ).fetchone()
    if project:
        task["project_name"] = project["name"]
        task["project_slug"] = project["slug"]

    # Fetch comments for this task
    comment_rows = conn.execute(
        """SELECT c.id, c.author, c.content, c.created_at
           FROM comments c
           WHERE c.target_type = 'task' AND c.target_id = ?
           ORDER BY c.created_at ASC""",
        (task_id,),
    ).fetchall()

    task["comments"] = [dict(c) for c in comment_rows]

    conn.close()
    return 200, {"task": task}
