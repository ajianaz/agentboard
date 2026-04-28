"""AgentBoard — Data export and import endpoints.

Endpoints:
    GET  /api/export          — export entire database as JSON
    GET  /api/export?project=slug — export single project
    POST /api/import          — import data from JSON export
"""

import json
from datetime import datetime, timezone
from db import get_db, gen_id
from api import router


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


def _row_to_dict(row, json_fields=()) -> dict:
    """Convert a sqlite3.Row to a plain dict, parsing listed JSON fields."""
    d = dict(row)
    for field in json_fields:
        raw = d.get(field)
        if isinstance(raw, str):
            try:
                d[field] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                d[field] = [] if field != "metadata" else {}
    return d


PROJECT_JSON_FIELDS = ("statuses", "priorities", "tags", "metadata")
TASK_JSON_FIELDS = ("tags", "metadata")
PAGE_JSON_FIELDS = ("metadata",)
AGENT_JSON_FIELDS = ("metadata",)


# ---------------------------------------------------------------------------
# GET /api/export
# GET /api/export?project=<slug>
# ---------------------------------------------------------------------------

@router.get("/api/export")
def export_data(params, query, body, headers):
    """Export the entire database (or a single project) as JSON."""
    project_slug = query.get("project", [None])[0]
    conn = get_db()

    try:
        if project_slug:
            # Export single project
            row = conn.execute(
                "SELECT * FROM projects WHERE slug = ?", (project_slug,)
            ).fetchone()
            if not row:
                return 404, {"error": f"Project '{project_slug}' not found",
                             "code": "NOT_FOUND"}
            projects_data = [_build_project_export(conn, row)]
        else:
            # Export all projects
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY position ASC, created_at ASC"
            ).fetchall()
            projects_data = [_build_project_export(conn, r) for r in rows]

        # Export all agents
        agent_rows = conn.execute(
            "SELECT * FROM agents ORDER BY name ASC"
        ).fetchall()
        agents = [_row_to_dict(r, AGENT_JSON_FIELDS) for r in agent_rows]

        return 200, {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "projects": projects_data,
            "agents": agents,
        }
    finally:
        conn.close()


def _build_project_export(conn, project_row) -> dict:
    """Build a single project dict with all related data (tasks, pages, comments)."""
    project = _row_to_dict(project_row, PROJECT_JSON_FIELDS)
    pid = project["id"]

    # Tasks
    task_rows = conn.execute(
        "SELECT * FROM tasks WHERE project_id = ? ORDER BY position ASC",
        (pid,),
    ).fetchall()
    tasks = [_row_to_dict(r, TASK_JSON_FIELDS) for r in task_rows]

    # Pages (with content)
    page_rows = conn.execute(
        "SELECT * FROM pages WHERE project_id = ? ORDER BY position ASC",
        (pid,),
    ).fetchall()
    pages = [_row_to_dict(r, PAGE_JSON_FIELDS) for r in page_rows]

    # Comments for tasks in this project
    task_ids = [t["id"] for t in tasks]
    page_ids = [p["id"] for p in pages]

    comments = []
    if task_ids:
        placeholders = ",".join("?" for _ in task_ids)
        comment_rows = conn.execute(
            f"SELECT * FROM comments WHERE target_type = 'task' AND target_id IN ({placeholders}) ORDER BY created_at ASC",
            task_ids,
        ).fetchall()
        comments.extend(dict(r) for r in comment_rows)

    if page_ids:
        placeholders = ",".join("?" for _ in page_ids)
        comment_rows = conn.execute(
            f"SELECT * FROM comments WHERE target_type = 'page' AND target_id IN ({placeholders}) ORDER BY created_at ASC",
            page_ids,
        ).fetchall()
        comments.extend(dict(r) for r in comment_rows)

    # Activity for this project
    activity_rows = conn.execute(
        "SELECT * FROM activity WHERE project_id = ? ORDER BY created_at DESC",
        (pid,),
    ).fetchall()
    activity = []
    for r in activity_rows:
        a = dict(r)
        raw_detail = a.get("detail")
        if isinstance(raw_detail, str):
            try:
                a["detail"] = json.loads(raw_detail)
            except (json.JSONDecodeError, ValueError):
                a["detail"] = {}
        activity.append(a)

    project["tasks"] = tasks
    project["pages"] = pages
    project["comments"] = comments
    project["activity"] = activity

    return project


# ---------------------------------------------------------------------------
# POST /api/import
# ---------------------------------------------------------------------------

@router.post("/api/import")
def import_data(params, query, body, headers):
    """Import data from a JSON export.

    Body: {"data": {...export format...}}

    Projects: upsert by slug.
    Tasks: always create new (generate new IDs).
    Pages: always create new (generate new IDs, remap parent_id).
    Agents: upsert by id.
    Comments: always create new (remap target_id for tasks/pages).
    """
    data = _parse_body(body)
    if data is None:
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    export = data.get("data")
    if not export or not isinstance(export, dict):
        return 400, {"error": "Request body must contain a 'data' field with export JSON",
                      "code": "VALIDATION_ERROR"}

    conn = get_db()
    imported = {"projects": 0, "tasks": 0, "pages": 0, "agents": 0}

    try:
        # ------------------------------------------------------------------
        # 1. Import agents (upsert by id) — no FK dependencies
        # ------------------------------------------------------------------
        for agent in export.get("agents") or []:
            agent_id = str(agent.get("id", "")).strip().lower()
            if not agent_id:
                continue
            existing = conn.execute(
                "SELECT id FROM agents WHERE id = ?", (agent_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE agents SET name=?, role=?, avatar=?, color=?,
                       is_active=?, metadata=?, created_at=datetime('now')
                       WHERE id = ?""",
                    (agent.get("name", ""),
                     agent.get("role", ""),
                     agent.get("avatar", "🤖"),
                     agent.get("color", "#3b82f6"),
                     1 if agent.get("is_active", 1) else 0,
                     json.dumps(agent.get("metadata", {})),
                     agent_id),
                )
            else:
                conn.execute(
                    """INSERT INTO agents (id, name, role, avatar, color, is_active, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (agent_id,
                     agent.get("name", ""),
                     agent.get("role", ""),
                     agent.get("avatar", "🤖"),
                     agent.get("color", "#3b82f6"),
                     1 if agent.get("is_active", 1) else 0,
                     json.dumps(agent.get("metadata", {}))),
                )
            imported["agents"] += 1

        # ------------------------------------------------------------------
        # 2. Import projects (upsert by slug) — track old→new id mapping
        # ------------------------------------------------------------------
        # Maps old project ID → current (new or existing) project ID
        project_id_map = {}

        for proj_export in export.get("projects") or []:
            slug = proj_export.get("slug", "")
            old_pid = proj_export.get("id", "")

            existing = conn.execute(
                "SELECT id FROM projects WHERE slug = ?", (slug,)
            ).fetchone()

            if existing:
                new_pid = existing["id"]
                conn.execute(
                    """UPDATE projects SET name=?, description=?, icon=?, color=?,
                       position=?, statuses=?, priorities=?, tags=?, metadata=?,
                       updated_at=datetime('now')
                       WHERE id = ?""",
                    (proj_export.get("name", ""),
                     proj_export.get("description", ""),
                     proj_export.get("icon", "📋"),
                     proj_export.get("color", "#3b82f6"),
                     proj_export.get("position", 0),
                     json.dumps(proj_export.get("statuses", [])),
                     json.dumps(proj_export.get("priorities", [])),
                     json.dumps(proj_export.get("tags", [])),
                     json.dumps(proj_export.get("metadata", {})),
                     new_pid),
                )
            else:
                new_pid = gen_id()
                conn.execute(
                    """INSERT INTO projects
                       (id, name, slug, description, icon, color, position,
                        statuses, priorities, tags, metadata, created_by, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (new_pid,
                     proj_export.get("name", ""),
                     slug,
                     proj_export.get("description", ""),
                     proj_export.get("icon", "📋"),
                     proj_export.get("color", "#3b82f6"),
                     proj_export.get("position", 0),
                     json.dumps(proj_export.get("statuses", [])),
                     json.dumps(proj_export.get("priorities", [])),
                     json.dumps(proj_export.get("tags", [])),
                     json.dumps(proj_export.get("metadata", {})),
                     proj_export.get("created_by")),
                )

            project_id_map[old_pid] = new_pid
            imported["projects"] += 1

        # ------------------------------------------------------------------
        # 3. Import pages (create new, remap parent_id)
        #    Maps old page ID → new page ID
        # ------------------------------------------------------------------
        page_id_map = {}

        for proj_export in export.get("projects") or []:
            old_pid = proj_export.get("id", "")
            new_pid = project_id_map.get(old_pid)
            if not new_pid:
                continue

            # First pass: create all pages (parent_id may be old ID)
            for page in proj_export.get("pages") or []:
                old_page_id = page.get("id", "")
                new_page_id = gen_id()
                page_id_map[old_page_id] = new_page_id

                old_parent = page.get("parent_id")
                # Will remap parent_id in second pass
                conn.execute(
                    """INSERT INTO pages
                       (id, project_id, parent_id, title, content, icon,
                        position, depth, is_expanded, metadata, created_by,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (new_page_id, new_pid, old_parent,
                     page.get("title", "Untitled"),
                     page.get("content", ""),
                     page.get("icon", "📄"),
                     page.get("position", 0),
                     page.get("depth", 0),
                     1 if page.get("is_expanded", 1) else 0,
                     json.dumps(page.get("metadata", {})),
                     page.get("created_by")),
                )
                imported["pages"] += 1

        # Second pass: remap parent_id from old → new page IDs
        for old_page_id, new_page_id in page_id_map.items():
            conn.execute(
                "UPDATE pages SET parent_id = ? WHERE id = ? AND parent_id IS NOT NULL",
                (page_id_map.get(conn.execute(
                    "SELECT parent_id FROM pages WHERE id = ?", (new_page_id,)
                ).fetchone()["parent_id"]), new_page_id),
            )
        # Actually, let's do this more simply:
        for old_page_id, new_page_id in page_id_map.items():
            row = conn.execute(
                "SELECT parent_id FROM pages WHERE id = ?", (new_page_id,)
            ).fetchone()
            if row and row["parent_id"]:
                old_parent = row["parent_id"]
                new_parent = page_id_map.get(old_parent)
                if new_parent and new_parent != old_parent:
                    conn.execute(
                        "UPDATE pages SET parent_id = ? WHERE id = ?",
                        (new_parent, new_page_id),
                    )

        # ------------------------------------------------------------------
        # 4. Import tasks (create new)
        #    Maps old task ID → new task ID
        # ------------------------------------------------------------------
        task_id_map = {}

        for proj_export in export.get("projects") or []:
            old_pid = proj_export.get("id", "")
            new_pid = project_id_map.get(old_pid)
            if not new_pid:
                continue

            for task in proj_export.get("tasks") or []:
                old_task_id = task.get("id", "")
                new_task_id = gen_id()
                task_id_map[old_task_id] = new_task_id

                conn.execute(
                    """INSERT INTO tasks
                       (id, project_id, title, description, status, priority,
                        assignee, tags, position, due_date, started_at,
                        completed_at, metadata, created_by,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                    (new_task_id, new_pid,
                     task.get("title", ""),
                     task.get("description", ""),
                     task.get("status", "todo"),
                     task.get("priority", "none"),
                     task.get("assignee", ""),
                     json.dumps(task.get("tags", [])),
                     task.get("position", 0),
                     task.get("due_date"),
                     task.get("started_at"),
                     task.get("completed_at"),
                     json.dumps(task.get("metadata", {})),
                     task.get("created_by")),
                )
                imported["tasks"] += 1

        # ------------------------------------------------------------------
        # 5. Import comments (create new, remap target_id for tasks/pages)
        # ------------------------------------------------------------------
        for proj_export in export.get("projects") or []:
            for comment in proj_export.get("comments") or []:
                target_type = comment.get("target_type", "task")
                old_target_id = comment.get("target_id", "")

                if target_type == "task":
                    new_target_id = task_id_map.get(old_target_id)
                elif target_type == "page":
                    new_target_id = page_id_map.get(old_target_id)
                else:
                    continue

                if not new_target_id:
                    continue

                conn.execute(
                    """INSERT INTO comments
                       (id, target_type, target_id, author, content, created_at)
                       VALUES (?, ?, ?, ?, ?, datetime('now'))""",
                    (gen_id(), target_type, new_target_id,
                     comment.get("author", ""),
                     comment.get("content", "")),
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return 200, {"imported": imported}
