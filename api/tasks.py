"""AgentBoard — Task CRUD, HITL transitions, cross-project queries, and hierarchy.

Endpoints:
    GET    /api/projects/{slug}/tasks           — list tasks in project
    POST   /api/projects/{slug}/tasks           — create task
    PATCH  /api/tasks/{id}                      — update task (HITL transitions)
    DELETE /api/tasks/{id}                      — delete task
    GET    /api/tasks?project=all               — cross-project tasks
    GET    /api/tasks/{id}                      — single task with comments
    GET    /api/tasks/{id}/children             — subtasks of a parent task
    GET    /api/projects/{slug}/tasks/tree      — hierarchical tree view
"""

import json
from db import get_db, gen_id
from api import router
from api.validation import (
    validate_enum, validate_title, validate_text, validate_task_type,
    VALID_STATUSES, VALID_PRIORITIES,
    MAX_TITLE_LENGTH, MAX_DESCRIPTION_LENGTH,
)
from webhook import on_task_created, on_task_assigned, on_task_status_changed, on_task_comment
from event_bus import publish


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_body(body: bytes) -> dict:
    """Safely parse JSON body. Returns empty dict on empty body, None on invalid JSON."""
    if not body:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None


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


def _compute_depth(conn, parent_id: str | None) -> int:
    """Compute depth for a task based on its parent's depth.

    Root tasks (no parent) get depth=0.
    Children get parent.depth + 1.
    """
    if not parent_id:
        return 0
    parent = conn.execute("SELECT depth FROM tasks WHERE id = ?", (parent_id,)).fetchone()
    if not parent:
        return 0
    return (parent["depth"] or 0) + 1


def _cascade_depth(conn, task_id: str, new_depth: int):
    """Recursively update depth for all descendants of a task.

    Called when a task's parent_id changes or a task is created with a parent.
    Uses iterative approach to avoid deep recursion.
    """
    # BFS: process children at each level
    queue = [(task_id, new_depth)]
    while queue:
        current_id, current_depth = queue.pop(0)
        children = conn.execute(
            "SELECT id FROM tasks WHERE parent_id = ?", (current_id,)
        ).fetchall()
        for child in children:
            child_depth = current_depth + 1
            conn.execute(
                "UPDATE tasks SET depth = ? WHERE id = ?", (child_depth, child["id"])
            )
            queue.append((child["id"], child_depth))


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
    # repurposed → todo (content repurposed for new use)
    ("repurposed", "todo"): ("repurposed", "Task repurposed and moved to To Do"),
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

    # Filter by type
    type_filter = _get_first(query.get("type"))
    if type_filter:
        conditions.append("t.type = ?")
        sql_params.append(type_filter)

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
    if data is None:
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    actor = headers.get("x-actor", "owner")

    conn = get_db()

    # Resolve project
    project = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not project:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project_id = project["id"]

    # Validate title
    title, title_err = validate_title(data.get("title"), MAX_TITLE_LENGTH, "Task title")
    if title_err:
        conn.close()
        return 400, {"error": title_err, "code": "VALIDATION_ERROR"}

    description = validate_text(data.get("description"), MAX_DESCRIPTION_LENGTH, "Task description")
    status = validate_enum(data.get("status"), VALID_STATUSES)
    if status is None and data.get("status"):
        raise ValueError(f"Invalid status: {data['status']}")
    status = status or "todo"
    priority = validate_enum(data.get("priority"), VALID_PRIORITIES)
    if priority is None and data.get("priority"):
        raise ValueError(f"Invalid priority: {data['priority']}")
    priority = priority or "none"
    task_type, type_err = validate_task_type(data.get("type"))
    if type_err:
        conn.close()
        return 400, {"error": type_err, "code": "VALIDATION_ERROR"}
    task_type = task_type or "task"
    assignee = validate_text(data.get("assignee"), 200, "assignee")
    tags = data.get("tags") or []
    due_date = validate_text(data.get("due_date"), 20, "due_date") or None
    parent_id = validate_text(data.get("parent_id"), 20, "parent_id") or None
    git_branch = validate_text(data.get("git_branch"), 200, "git_branch") or ""

    # Validate parent_id exists AND belongs to same project
    if parent_id:
        parent = conn.execute(
            "SELECT id, project_id FROM tasks WHERE id = ?", (parent_id,)
        ).fetchone()
        if not parent:
            conn.close()
            return 400, {"error": f"Parent task '{parent_id}' not found", "code": "VALIDATION_ERROR"}
        if parent["project_id"] != project_id:
            conn.close()
            return 400, {"error": "Parent task must belong to the same project", "code": "VALIDATION_ERROR"}

    # Compute depth based on parent
    depth = _compute_depth(conn, parent_id)

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

    # Atomic position assignment: compute MAX+1 in the same statement as INSERT
    # to prevent race conditions with concurrent task creation
    conn.execute(
        """INSERT INTO tasks
           (id, project_id, parent_id, title, description, status, type, priority, assignee,
            tags, position, due_date, started_at, completed_at, metadata, created_by, depth, git_branch)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   (SELECT COALESCE(MAX(position), 0) + 1 FROM tasks WHERE project_id = ? AND status = ?),
                   ?, ?, ?, ?, ?, ?, ?)""",
        (task_id, project_id, parent_id, title, description, status, task_type, priority, assignee,
         json.dumps(tags), project_id, status, due_date, started_at, completed_at,
         json.dumps({}), created_by, depth, git_branch),
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

    # Fire webhook notification
    on_task_created(task, actor, slug)

    publish("task_created", {"id": task_id, "project": slug, "title": task.get("title", "")})

    return 201, {"task": task}


# ---------------------------------------------------------------------------
# PATCH /api/tasks/{id}
# ---------------------------------------------------------------------------

@router.patch("/api/tasks/{id}")
def update_task(params, query, body, headers):
    task_id = params["id"]
    data = _parse_body(body)
    if data is None:
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
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
        new_title, title_err = validate_title(data["title"], MAX_TITLE_LENGTH, "Task title")
        if title_err:
            conn.close()
            return 400, {"error": title_err, "code": "VALIDATION_ERROR"}
        updates["title"] = new_title
        detail_changes["title"] = new_title

    # Description
    if "description" in data and data["description"] is not None:
        updates["description"] = validate_text(data["description"], MAX_DESCRIPTION_LENGTH, "Task description")

    # Status — HITL transitions
    if "status" in data and data["status"] is not None:
        new_status = validate_enum(data["status"], VALID_STATUSES)
        if new_status is None:
            conn.close()
            return 400, {"error": f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}", "code": "VALIDATION_ERROR"}
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
        new_priority = validate_enum(data["priority"], VALID_PRIORITIES)
        if new_priority is None:
            conn.close()
            return 400, {"error": f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}", "code": "VALIDATION_ERROR"}
        updates["priority"] = new_priority

    # Type
    if "type" in data and data["type"] is not None:
        new_type, type_err = validate_task_type(data["type"])
        if type_err:
            conn.close()
            return 400, {"error": type_err, "code": "VALIDATION_ERROR"}
        updates["type"] = new_type

    # Assignee
    if "assignee" in data and data["assignee"] is not None:
        new_assignee = str(data["assignee"]).strip()
        updates["assignee"] = new_assignee
        if new_assignee != row["assignee"]:
            detail_changes["assignee"] = new_assignee

    # Parent ID — with cascade depth update
    if "parent_id" in data:
        new_parent = validate_text(data["parent_id"], 20, "parent_id") or None
        old_parent = row["parent_id"]
        if new_parent != old_parent:
            # Validate new parent exists and belongs to same project
            if new_parent:
                parent = conn.execute(
                    "SELECT id, project_id FROM tasks WHERE id = ? AND id != ?",
                    (new_parent, task_id),
                ).fetchone()
                if not parent:
                    conn.close()
                    return 400, {"error": f"Parent task '{new_parent}' not found", "code": "VALIDATION_ERROR"}
                if parent["project_id"] != project_id:
                    conn.close()
                    return 400, {"error": "Parent task must belong to the same project", "code": "VALIDATION_ERROR"}
                # Prevent circular reference: walk UP ancestors from new_parent
                # to check if task_id appears (meaning new_parent is a descendant)
                ancestor_id = new_parent
                visited = set()
                while ancestor_id:
                    if ancestor_id == task_id:
                        conn.close()
                        return 400, {"error": "Circular reference: cannot set a descendant as parent", "code": "VALIDATION_ERROR"}
                    if ancestor_id in visited:
                        break  # safety: existing circular data in DB
                    visited.add(ancestor_id)
                    ancestor_row = conn.execute("SELECT parent_id FROM tasks WHERE id = ?", (ancestor_id,)).fetchone()
                    ancestor_id = ancestor_row["parent_id"] if ancestor_row else None

            updates["parent_id"] = new_parent
            updates["depth"] = _compute_depth(conn, new_parent)

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

    # Git branch
    if "git_branch" in data:
        updates["git_branch"] = validate_text(data["git_branch"], 200, "git_branch") or ""

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

    # Cascade depth update to all children when parent changed
    if "parent_id" in updates:
        new_depth = updates.get("depth", 0)
        _cascade_depth(conn, task_id, new_depth)

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

    # Resolve project slug for webhook
    project_row = conn.execute(
        "SELECT slug FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    project_slug = project_row["slug"] if project_row else ""

    conn.close()

    # Fire webhook notifications (async, non-blocking)
    new_status = updates.get("status")
    if new_status and new_status != old_status:
        on_task_status_changed(task, old_status, new_status, actor, project_slug)

    new_assignee = updates.get("assignee")
    if new_assignee and new_assignee != row["assignee"]:
        on_task_assigned(task, row["assignee"], new_assignee, actor, project_slug)

    if "comment" in data and data["comment"]:
        comment_text = str(data["comment"]).strip()
        if comment_text:
            on_task_comment(task, actor, comment_text, project_slug)

    publish("task_updated", {"id": task_id, "project": project_slug, "title": task.get("title", "")})

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

    publish("task_deleted", {"id": task_id, "project": slug})

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

    # Type filter
    type_filter = _get_first(query.get("type"))
    if type_filter:
        conditions.append("t.type = ?")
        sql_params.append(type_filter)

    # Git branch filter
    branch_filter = _get_first(query.get("branch"))
    if branch_filter:
        conditions.append("t.git_branch = ?")
        sql_params.append(branch_filter)

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


# ---------------------------------------------------------------------------
# GET /api/tasks/{id}/children — subtasks of a parent task
# ---------------------------------------------------------------------------

@router.get("/api/tasks/{id}/children")
def list_subtasks(params, query, body, headers):
    parent_id = params["id"]
    conn = get_db()

    # Verify parent task exists
    parent = conn.execute("SELECT id FROM tasks WHERE id = ?", (parent_id,)).fetchone()
    if not parent:
        conn.close()
        return 404, {"error": f"Task '{parent_id}' not found", "code": "NOT_FOUND"}

    rows = conn.execute(
        """SELECT t.* FROM tasks t
           WHERE t.parent_id = ?
           ORDER BY t.status ASC, t.position ASC, t.created_at ASC""",
        (parent_id,),
    ).fetchall()

    children = [_task_row_to_dict(r) for r in rows]
    conn.close()
    return 200, {"tasks": children}


# ---------------------------------------------------------------------------
# GET /api/projects/{slug}/tasks/tree — hierarchical tree view
# ---------------------------------------------------------------------------

@router.get("/api/projects/{slug}/tasks/tree")
def list_project_tasks_tree(params, query, body, headers):
    """Return all tasks in a project as a nested tree structure.

    Query params:
        type — filter by task type (e.g. type=mission to show only missions)
        status — filter by status
        depth_max — max depth to include (default: no limit)
    """
    slug = params["slug"]
    conn = get_db()

    project = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not project:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project_id = project["id"]

    # Build conditions
    conditions = ["t.project_id = ?"]
    sql_params: list = [project_id]

    type_filter = _get_first(query.get("type"))
    if type_filter:
        conditions.append("t.type = ?")
        sql_params.append(type_filter)

    status_filter = _get_first(query.get("status"))
    if status_filter:
        conditions.append("t.status = ?")
        sql_params.append(status_filter)

    depth_max = _get_first(query.get("depth_max"))
    if depth_max:
        try:
            conditions.append("t.depth <= ?")
            sql_params.append(int(depth_max))
        except ValueError:
            pass

    where_clause = " AND ".join(conditions)

    # Fetch all matching tasks ordered by depth, then position
    rows = conn.execute(
        f"""SELECT t.* FROM tasks t
            WHERE {where_clause}
            ORDER BY t.depth ASC, t.position ASC, t.created_at ASC""",
        sql_params,
    ).fetchall()

    # Build tree structure
    all_tasks = {}
    for r in rows:
        task = _task_row_to_dict(r)
        task["children"] = []
        all_tasks[task["id"]] = task

    roots = []
    for task in all_tasks.values():
        parent_id = task.get("parent_id")
        if parent_id and parent_id in all_tasks:
            all_tasks[parent_id]["children"].append(task)
        else:
            roots.append(task)

    conn.close()
    return 200, {"tree": roots, "total": len(all_tasks)}
