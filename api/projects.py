"""AgentBoard — Project CRUD, stats, and setup endpoints.

Endpoints:
    GET    /api/projects             — list active projects
    GET    /api/projects?include_archived=1 — list including archived
    GET    /api/projects/{slug}      — project detail + task stats
    POST   /api/projects             — create project
    PATCH  /api/projects/{slug}      — update project
    DELETE /api/projects/{slug}      — archive (soft delete)
    POST   /api/projects/{slug}/restore — unarchive
    GET    /api/stats                — cross-project summary
    POST   /api/setup                — first-run setup
"""

import json
from db import get_db, gen_id, slugify
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


def _project_row_to_dict(row) -> dict:
    """Convert a project Row to a plain dict with JSON fields parsed."""
    d = dict(row)
    for field in ("statuses", "priorities", "tags", "metadata"):
        raw = d.get(field)
        if isinstance(raw, str):
            try:
                d[field] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                d[field] = [] if field != "metadata" else {}
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


# ---------------------------------------------------------------------------
# GET /api/projects
# GET /api/projects?include_archived=1
# ---------------------------------------------------------------------------

@router.get("/api/projects")
def list_projects(params, query, body, headers):
    conn = get_db()
    include_archived = "1" in query.get("include_archived", [])

    if include_archived:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY position ASC, created_at ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM projects WHERE is_archived = 0 ORDER BY position ASC, created_at ASC"
        ).fetchall()

    projects = [_project_row_to_dict(r) for r in rows]
    conn.close()
    return 200, {"projects": projects}


# ---------------------------------------------------------------------------
# GET /api/projects/{slug}
# ---------------------------------------------------------------------------

@router.get("/api/projects/{slug}")
def get_project(params, query, body, headers):
    slug = params["slug"]
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM projects WHERE slug = ?", (slug,)
    ).fetchone()

    if not row:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project = _project_row_to_dict(row)

    # Task counts grouped by status
    stats_rows = conn.execute(
        """SELECT status, COUNT(*) as count
           FROM tasks WHERE project_id = ?
           GROUP BY status""",
        (project["id"],),
    ).fetchall()
    task_stats = {r["status"]: r["count"] for r in stats_rows}
    total_tasks = sum(task_stats.values())

    conn.close()
    return 200, {
        "project": project,
        "task_stats": task_stats,
        "total_tasks": total_tasks,
    }


# ---------------------------------------------------------------------------
# POST /api/projects
# ---------------------------------------------------------------------------

@router.post("/api/projects")
def create_project(params, query, body, headers):
    data = _parse_body(body)
    name = (data.get("name") or "").strip()

    if not name:
        return 400, {"error": "Project name is required", "code": "VALIDATION_ERROR"}

    slug = slugify(name)
    if not slug or slug == "untitled":
        return 400, {"error": "Could not generate a valid slug from name", "code": "VALIDATION_ERROR"}

    # Check for optional explicit slug in the body (for disambiguation)
    explicit_slug = (data.get("slug") or "").strip()
    if explicit_slug:
        explicit_slug = slugify(explicit_slug)
        if explicit_slug and explicit_slug != "untitled":
            slug = explicit_slug

    actor = headers.get("x-actor", "owner")

    # Default JSON fields
    default_statuses = [
        {"key": "proposed", "label": "Proposed", "color": "#f59e0b"},
        {"key": "todo", "label": "To Do", "color": "#6b7280"},
        {"key": "in_progress", "label": "In Progress", "color": "#3b82f6"},
        {"key": "review", "label": "Review", "color": "#8b5cf6"},
        {"key": "done", "label": "Done", "color": "#22c55e"},
    ]
    default_priorities = [
        {"key": "critical", "label": "Critical", "color": "#ef4444"},
        {"key": "high", "label": "High", "color": "#f97316"},
        {"key": "medium", "label": "Medium", "color": "#eab308"},
        {"key": "low", "label": "Low", "color": "#22c55e"},
        {"key": "none", "label": "None", "color": "#6b7280"},
    ]

    conn = get_db()

    # Validate slug uniqueness
    existing = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if existing:
        # Try appending a numeric suffix
        for i in range(2, 100):
            candidate = f"{slug}-{i}"
            existing = conn.execute("SELECT id FROM projects WHERE slug = ?", (candidate,)).fetchone()
            if not existing:
                slug = candidate
                break
        else:
            conn.close()
            return 409, {"error": f"Slug '{slug}' is already in use", "code": "SLUG_CONFLICT"}

    # Determine position (append to end)
    pos_row = conn.execute("SELECT MAX(position) as max_pos FROM projects").fetchone()
    position = (pos_row["max_pos"] or 0) + 1

    project_id = gen_id()
    description = (data.get("description") or "").strip()
    icon = (data.get("icon") or "📋").strip()
    color = (data.get("color") or "#3b82f6").strip()
    statuses = data.get("statuses") or default_statuses
    priorities = data.get("priorities") or default_priorities
    tags = data.get("tags") or []
    metadata = data.get("metadata") or {}

    conn.execute(
        """INSERT INTO projects
           (id, name, slug, description, icon, color, position, statuses,
            priorities, tags, metadata, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, name, slug, description, icon, color, position,
         json.dumps(statuses), json.dumps(priorities), json.dumps(tags),
         json.dumps(metadata), actor),
    )

    _log_activity(conn, project_id, "project", project_id, "created", actor,
                  {"name": name, "slug": slug})

    conn.commit()

    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    project = _project_row_to_dict(row)
    conn.close()

    return 201, {"project": project}


# ---------------------------------------------------------------------------
# PATCH /api/projects/{slug}
# ---------------------------------------------------------------------------

@router.patch("/api/projects/{slug}")
def update_project(params, query, body, headers):
    slug = params["slug"]
    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project_id = row["id"]
    updates = {}
    detail_changes = {}

    # Name
    if "name" in data and data["name"] is not None:
        new_name = str(data["name"]).strip()
        if not new_name:
            conn.close()
            return 400, {"error": "Project name cannot be empty", "code": "VALIDATION_ERROR"}
        updates["name"] = new_name
        detail_changes["name"] = new_name

    # Slug (renaming)
    if "slug" in data and data["slug"] is not None:
        new_slug = slugify(str(data["slug"]).strip())
        if not new_slug or new_slug == "untitled":
            conn.close()
            return 400, {"error": "Invalid slug", "code": "VALIDATION_ERROR"}
        if new_slug != slug:
            dup = conn.execute("SELECT id FROM projects WHERE slug = ? AND id != ?", (new_slug, project_id)).fetchone()
            if dup:
                conn.close()
                return 409, {"error": f"Slug '{new_slug}' is already in use", "code": "SLUG_CONFLICT"}
            updates["slug"] = new_slug
            detail_changes["slug"] = new_slug

    # Simple fields
    for field in ("description", "icon", "color"):
        if field in data and data[field] is not None:
            updates[field] = str(data[field]).strip()

    # Position
    if "position" in data and data["position"] is not None:
        try:
            updates["position"] = int(data["position"])
        except (ValueError, TypeError):
            pass

    # JSON fields
    for field in ("statuses", "priorities", "tags", "metadata"):
        if field in data and data[field] is not None:
            updates[field] = json.dumps(data[field])

    if not updates:
        conn.close()
        return 200, {"project": _project_row_to_dict(row)}

    # Build SET clause
    set_parts = []
    set_values = []
    for key, val in updates.items():
        set_parts.append(f"{key} = ?")
        set_values.append(val)
    set_values.append(project_id)

    conn.execute(
        f"UPDATE projects SET {', '.join(set_parts)}, updated_at = datetime('now') WHERE id = ?",
        set_values,
    )

    _log_activity(conn, project_id, "project", project_id, "updated", actor, detail_changes)

    conn.commit()
    updated = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    project = _project_row_to_dict(updated)
    conn.close()

    return 200, {"project": project}


# ---------------------------------------------------------------------------
# DELETE /api/projects/{slug}  (soft delete / archive)
# ---------------------------------------------------------------------------

@router.delete("/api/projects/{slug}")
def archive_project(params, query, body, headers):
    slug = params["slug"]
    actor = headers.get("x-actor", "owner")

    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    if row["is_archived"]:
        conn.close()
        return 400, {"error": "Project is already archived", "code": "ALREADY_ARCHIVED"}

    conn.execute(
        "UPDATE projects SET is_archived = 1, updated_at = datetime('now') WHERE id = ?",
        (row["id"],),
    )

    _log_activity(conn, row["id"], "project", row["id"], "archived", actor,
                  {"name": row["name"], "slug": slug})

    conn.commit()
    project = _project_row_to_dict(row)
    project["is_archived"] = 1
    conn.close()

    return 200, {"project": project}


# ---------------------------------------------------------------------------
# POST /api/projects/{slug}/restore
# ---------------------------------------------------------------------------

@router.post("/api/projects/{slug}/restore")
def restore_project(params, query, body, headers):
    slug = params["slug"]
    actor = headers.get("x-actor", "owner")

    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    if not row["is_archived"]:
        conn.close()
        return 400, {"error": "Project is not archived", "code": "NOT_ARCHIVED"}

    conn.execute(
        "UPDATE projects SET is_archived = 0, updated_at = datetime('now') WHERE id = ?",
        (row["id"],),
    )

    _log_activity(conn, row["id"], "project", row["id"], "restored", actor,
                  {"name": row["name"], "slug": slug})

    conn.commit()
    project = _project_row_to_dict(row)
    project["is_archived"] = 0
    conn.close()

    return 200, {"project": project}


# ---------------------------------------------------------------------------
# GET /api/stats — cross-project summary
# ---------------------------------------------------------------------------

@router.get("/api/stats")
def get_stats(params, query, body, headers):
    conn = get_db()

    # Overall totals
    totals = conn.execute(
        """SELECT
               COUNT(*) as total_tasks,
               SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done_tasks,
               SUM(CASE WHEN status = 'proposed' THEN 1 ELSE 0 END) as proposed_tasks,
               SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tasks,
               SUM(CASE WHEN status = 'review' THEN 1 ELSE 0 END) as review_tasks
           FROM tasks"""
    ).fetchone()

    # Per-project breakdown
    project_rows = conn.execute(
        """SELECT
               p.id, p.name, p.slug, p.icon, p.color, p.is_archived,
               COUNT(t.id) as total_tasks,
               SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done_tasks,
               SUM(CASE WHEN t.status = 'proposed' THEN 1 ELSE 0 END) as proposed_tasks,
               SUM(CASE WHEN t.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tasks,
               SUM(CASE WHEN t.status = 'review' THEN 1 ELSE 0 END) as review_tasks
           FROM projects p
           LEFT JOIN tasks t ON t.project_id = p.id
           WHERE p.is_archived = 0
           GROUP BY p.id
           ORDER BY p.position ASC"""
    ).fetchall()

    projects = []
    for r in project_rows:
        total = r["total_tasks"] or 0
        done = r["done_tasks"] or 0
        projects.append({
            "id": r["id"],
            "name": r["name"],
            "slug": r["slug"],
            "icon": r["icon"],
            "color": r["color"],
            "total_tasks": total,
            "done_tasks": done,
            "proposed_tasks": r["proposed_tasks"] or 0,
            "in_progress_tasks": r["in_progress_tasks"] or 0,
            "review_tasks": r["review_tasks"] or 0,
            "completion_pct": round(done / total * 100, 1) if total > 0 else 0,
        })

    total_tasks = totals["total_tasks"] or 0
    done_tasks = totals["done_tasks"] or 0

    stats = {
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "proposed_tasks": totals["proposed_tasks"] or 0,
        "in_progress_tasks": totals["in_progress_tasks"] or 0,
        "review_tasks": totals["review_tasks"] or 0,
        "completion_pct": round(done_tasks / total_tasks * 100, 1) if total_tasks > 0 else 0,
        "projects": projects,
    }

    conn.close()
    return 200, stats


# ---------------------------------------------------------------------------
# POST /api/setup — first-run setup
# ---------------------------------------------------------------------------

@router.post("/api/setup")
def setup(params, query, body, headers):
    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    conn = get_db()

    # Check if any projects already exist
    existing = conn.execute("SELECT COUNT(*) as cnt FROM projects").fetchone()
    if existing["cnt"] > 0:
        conn.close()
        return 400, {"error": "Setup already completed — projects already exist",
                      "code": "SETUP_DONE"}

    name = (data.get("name") or "").strip() or "My Project"
    slug = slugify(name)

    # Ensure slug uniqueness (unlikely on first run, but safe)
    dup = conn.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
    if dup:
        slug = f"{slug}-1"

    description = (data.get("description") or "").strip()
    icon = (data.get("icon") or "📋").strip()
    color = (data.get("color") or "#3b82f6").strip()

    default_statuses = [
        {"key": "proposed", "label": "Proposed", "color": "#f59e0b"},
        {"key": "todo", "label": "To Do", "color": "#6b7280"},
        {"key": "in_progress", "label": "In Progress", "color": "#3b82f6"},
        {"key": "review", "label": "Review", "color": "#8b5cf6"},
        {"key": "done", "label": "Done", "color": "#22c55e"},
    ]
    default_priorities = [
        {"key": "critical", "label": "Critical", "color": "#ef4444"},
        {"key": "high", "label": "High", "color": "#f97316"},
        {"key": "medium", "label": "Medium", "color": "#eab308"},
        {"key": "low", "label": "Low", "color": "#22c55e"},
        {"key": "none", "label": "None", "color": "#6b7280"},
    ]

    statuses = data.get("statuses") or default_statuses
    priorities = data.get("priorities") or default_priorities

    project_id = gen_id()

    conn.execute(
        """INSERT INTO projects
           (id, name, slug, description, icon, color, position, statuses,
            priorities, tags, metadata, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, name, slug, description, icon, color, 0,
         json.dumps(statuses), json.dumps(priorities), json.dumps([]),
         json.dumps({}), actor),
    )

    _log_activity(conn, project_id, "project", project_id, "created", actor,
                  {"name": name, "slug": slug, "via": "setup"})

    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    project = _project_row_to_dict(row)
    conn.close()

    return 201, {"project": project}
