"""AgentBoard — Page CRUD, outline tree, and move endpoints.

Endpoints:
    GET    /api/pages                  — all pages across projects (grouped by project)
    GET    /api/projects/{slug}/pages  — flat list of pages (frontend builds tree)
    POST   /api/projects/{slug}/pages  — create page
    POST   /api/pages                  — create standalone page (no project)
    PATCH  /api/pages/{id}             — update page
    DELETE /api/pages/{id}             — delete page (CASCADE deletes children)
    POST   /api/pages/{id}/move        — move page (change parent/position)
"""

import json
from db import get_db, gen_id
from api import router, is_authenticated


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


def _page_row_to_dict(row) -> dict:
    """Convert a page Row to a plain dict with JSON fields parsed."""
    d = dict(row)
    for field in ("metadata",):
        raw = d.get(field)
        if isinstance(raw, str):
            try:
                d[field] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                d[field] = {}
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
# GET /api/pages — all pages across projects (grouped by project)
# ---------------------------------------------------------------------------

@router.get("/api/pages")
def list_all_pages(params, query, body, headers):
    """Return all pages grouped by project, for the global docs view.
    
    Unauthenticated: only public projects with public pages.
    Authenticated: show everything (respecting archived filter).
    """
    conn = get_db()
    authed = is_authenticated(headers)

    # Visibility filter for unauthenticated requests
    proj_vis = "" if authed else "AND p.visibility = 'public'"
    page_vis = "" if authed else "AND pg.visibility = 'public'"

    # Get all NON-ARCHIVED projects with their page counts
    projects = conn.execute(
        f"""SELECT p.id, p.slug, p.name, p.icon, p.color,
                  (SELECT COUNT(*) FROM pages c WHERE c.project_id = p.id AND c.parent_id IS NULL {page_vis}) as root_page_count
           FROM projects p
           WHERE p.is_archived = 0 {proj_vis}
           ORDER BY p.name ASC"""
    ).fetchall()

    result = []
    for proj in projects:
        if proj["root_page_count"] == 0:
            continue
        # Fetch all pages for this project (tree-ready order)
        rows = conn.execute(
            f"""SELECT p.*,
                      (SELECT COUNT(*) FROM pages c WHERE c.parent_id = p.id) as child_count
               FROM pages p
               WHERE p.project_id = ? {page_vis}
               ORDER BY p.parent_id IS NOT NULL, p.position ASC, p.created_at ASC""",
            (proj["id"],),
        ).fetchall()
        result.append({
            "project": {
                "slug": proj["slug"],
                "name": proj["name"],
                "icon": proj["icon"],
                "color": proj["color"],
                "visibility": proj["visibility"],
            },
            "pages": [_page_row_to_dict(r) for r in rows],
        })

    # Standalone pages (project_id IS NULL)
    standalone_rows = conn.execute(
        f"""SELECT p.*,
                  (SELECT COUNT(*) FROM pages c WHERE c.parent_id = p.id) as child_count
           FROM pages p
           WHERE p.project_id IS NULL {page_vis}
           ORDER BY p.parent_id IS NOT NULL, p.position ASC, p.created_at ASC"""
    ).fetchall()
    standalone_pages = [_page_row_to_dict(r) for r in standalone_rows]
    if standalone_pages:
        result.append({
            "project": {
                "slug": "__standalone__",
                "name": "Standalone Pages",
                "icon": "📝",
                "color": "#6b7280",
                "visibility": "public",
            },
            "pages": standalone_pages,
        })

    conn.close()
    return 200, {"projects": result}


# ---------------------------------------------------------------------------
# POST /api/pages — create standalone page (no project required)
# ---------------------------------------------------------------------------

@router.post("/api/pages")
def create_standalone_page(params, query, body, headers):
    """Create a page without a project (project_id = NULL).

    Requires authentication.
    """
    if not is_authenticated(headers):
        return 401, {"error": "Authentication required", "code": "AUTH_REQUIRED"}

    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    title = (data.get("title") or "Untitled").strip()
    content = (data.get("content") or "").strip()
    icon = (data.get("icon") or "📄").strip()
    parent_id = data.get("parent_id") or None
    visibility = (data.get("visibility") or "public").strip().lower()
    if visibility not in ("public", "hidden"):
        visibility = "public"

    # Validate parent_id belongs to another standalone page
    if parent_id:
        conn = get_db()
        parent = conn.execute("SELECT depth, project_id FROM pages WHERE id = ?", (parent_id,)).fetchone()
        if not parent:
            conn.close()
            return 400, {"error": f"Parent page '{parent_id}' not found", "code": "NOT_FOUND"}
        if parent["project_id"] is not None:
            conn.close()
            return 400, {"error": "Parent page belongs to a project — use project-scoped endpoint", "code": "VALIDATION_ERROR"}
        depth = parent["depth"] + 1
    else:
        conn = get_db()
        depth = 0

    # Auto-calculate position among standalone siblings
    pos_row = conn.execute(
        """SELECT MAX(position) as max_pos FROM pages
           WHERE project_id IS NULL AND parent_id IS ?""",
        (parent_id,),
    ).fetchone()
    position = (pos_row["max_pos"] or 0) + 1

    page_id = gen_id()

    conn.execute(
        """INSERT INTO pages
           (id, project_id, parent_id, title, content, icon, position, depth, visibility, created_by)
           VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (page_id, parent_id, title, content, icon, position, depth, visibility, actor),
    )

    _log_activity(conn, None, "page", page_id, "created", actor,
                  {"title": title, "standalone": True})

    conn.commit()

    row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    page = _page_row_to_dict(row)
    conn.close()

    return 201, {"page": page}


# ---------------------------------------------------------------------------
# GET /api/projects/{slug}/pages — flat list ordered for tree building
# ---------------------------------------------------------------------------

@router.get("/api/projects/{slug}/pages")
def list_pages(params, query, body, headers):
    slug = params["slug"]
    conn = get_db()
    authed = is_authenticated(headers)

    # Resolve project
    project = conn.execute("SELECT id, visibility FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not project:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    # Unauthenticated: deny access to hidden projects
    if not authed and project["visibility"] != "public":
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project_id = project["id"]
    page_vis = "" if authed else "AND p.visibility = 'public'"

    # Fetch all pages with child_count and ordered by parent_id (NULLs first), position
    rows = conn.execute(
        f"""SELECT p.*,
                  (SELECT COUNT(*) FROM pages c WHERE c.parent_id = p.id) as child_count
           FROM pages p
           WHERE p.project_id = ? {page_vis}
           ORDER BY p.parent_id IS NOT NULL, p.position ASC, p.created_at ASC""",
        (project_id,),
    ).fetchall()

    pages = [_page_row_to_dict(r) for r in rows]
    conn.close()
    return 200, {"pages": pages}


# ---------------------------------------------------------------------------
# POST /api/projects/{slug}/pages — create page
# ---------------------------------------------------------------------------

@router.post("/api/projects/{slug}/pages")
def create_page(params, query, body, headers):
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

    title = (data.get("title") or "Untitled").strip()
    content = (data.get("content") or "").strip()
    icon = (data.get("icon") or "📄").strip()
    parent_id = data.get("parent_id") or None

    # Calculate depth based on parent
    depth = 0
    if parent_id:
        parent = conn.execute("SELECT depth FROM pages WHERE id = ?", (parent_id,)).fetchone()
        if not parent:
            conn.close()
            return 400, {"error": f"Parent page '{parent_id}' not found", "code": "NOT_FOUND"}
        # Verify parent belongs to same project
        parent_proj = conn.execute("SELECT project_id FROM pages WHERE id = ?", (parent_id,)).fetchone()
        if parent_proj and parent_proj["project_id"] != project_id:
            conn.close()
            return 400, {"error": "Parent page belongs to a different project", "code": "VALIDATION_ERROR"}
        depth = parent["depth"] + 1

    # Auto-calculate position (max position among siblings + 1)
    pos_row = conn.execute(
        """SELECT MAX(position) as max_pos FROM pages
           WHERE project_id = ? AND parent_id IS ?""",
        (project_id, parent_id),
    ).fetchone()
    position = (pos_row["max_pos"] or 0) + 1

    page_id = gen_id()

    conn.execute(
        """INSERT INTO pages
           (id, project_id, parent_id, title, content, icon, position, depth, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (page_id, project_id, parent_id, title, content, icon, position, depth, actor),
    )

    _log_activity(conn, project_id, "page", page_id, "created", actor,
                  {"title": title, "depth": depth})

    conn.commit()

    row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    page = _page_row_to_dict(row)
    conn.close()

    return 201, {"page": page}


# ---------------------------------------------------------------------------
# PATCH /api/pages/{id} — update page
# ---------------------------------------------------------------------------

@router.patch("/api/pages/{id}")
def update_page(params, query, body, headers):
    page_id = params["id"]
    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    conn = get_db()

    row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Page '{page_id}' not found", "code": "NOT_FOUND"}

    project_id = row["project_id"]
    updates = {}
    detail_changes = {}

    # Title
    if "title" in data and data["title"] is not None:
        new_title = str(data["title"]).strip()
        updates["title"] = new_title
        detail_changes["title"] = new_title

    # Content
    if "content" in data and data["content"] is not None:
        updates["content"] = str(data["content"])

    # Icon
    if "icon" in data and data["icon"] is not None:
        updates["icon"] = str(data["icon"]).strip()

    # is_expanded
    if "is_expanded" in data and data["is_expanded"] is not None:
        try:
            updates["is_expanded"] = int(data["is_expanded"])
        except (ValueError, TypeError):
            pass

    # Metadata
    if "metadata" in data and data["metadata"] is not None:
        updates["metadata"] = json.dumps(data["metadata"])

    # Visibility (validated enum)
    if "visibility" in data and data["visibility"] is not None:
        vis = str(data["visibility"]).strip().lower()
        if vis not in ("public", "hidden"):
            conn.close()
            return 400, {"error": "visibility must be 'public' or 'hidden'", "code": "VALIDATION_ERROR"}
        updates["visibility"] = vis
        detail_changes["visibility"] = vis

    if not updates:
        conn.close()
        return 200, {"page": _page_row_to_dict(row)}

    # Build SET clause
    set_parts = []
    set_values = []
    for key, val in updates.items():
        set_parts.append(f"{key} = ?")
        set_values.append(val)
    set_values.append(page_id)

    conn.execute(
        f"UPDATE pages SET {', '.join(set_parts)}, updated_at = datetime('now') WHERE id = ?",
        set_values,
    )

    _log_activity(conn, project_id, "page", page_id, "updated", actor, detail_changes)

    conn.commit()
    updated = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    page = _page_row_to_dict(updated)
    conn.close()

    return 200, {"page": page}


# ---------------------------------------------------------------------------
# DELETE /api/pages/{id} — delete page (CASCADE deletes children via FK)
# ---------------------------------------------------------------------------

@router.delete("/api/pages/{id}")
def delete_page(params, query, body, headers):
    page_id = params["id"]
    actor = headers.get("x-actor", "owner")

    conn = get_db()

    row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Page '{page_id}' not found", "code": "NOT_FOUND"}

    project_id = row["project_id"]
    page_title = row["title"]

    # Count children that will be cascade-deleted
    child_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM pages WHERE parent_id = ?", (page_id,)
    ).fetchone()["cnt"]

    # Delete comments on this page
    conn.execute("DELETE FROM comments WHERE target_type = 'page' AND target_id = ?", (page_id,))

    # Delete the page (CASCADE will handle children via FK)
    conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))

    detail = {"title": page_title}
    if child_count > 0:
        detail["cascade_children"] = child_count

    _log_activity(conn, project_id, "page", page_id, "deleted", actor, detail)

    conn.commit()
    conn.close()

    return 200, {"deleted": True, "id": page_id}


# ---------------------------------------------------------------------------
# POST /api/pages/{id}/move — move page (change parent and/or position)
# ---------------------------------------------------------------------------

@router.post("/api/pages/{id}/move")
def move_page(params, query, body, headers):
    page_id = params["id"]
    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    new_parent_id = data.get("parent_id")  # None means root level
    new_position = data.get("position")

    if new_parent_id is None and new_position is None:
        return 400, {"error": "Must specify parent_id and/or position", "code": "VALIDATION_ERROR"}

    conn = get_db()

    row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Page '{page_id}' not found", "code": "NOT_FOUND"}

    project_id = row["project_id"]
    old_parent_id = row["parent_id"]
    old_depth = row["depth"]

    # Validate new parent if specified
    if new_parent_id is not None:
        if new_parent_id == page_id:
            conn.close()
            return 400, {"error": "Cannot move page under itself", "code": "VALIDATION_ERROR"}
        parent = conn.execute("SELECT * FROM pages WHERE id = ?", (new_parent_id,)).fetchone()
        if not parent:
            conn.close()
            return 400, {"error": f"Parent page '{new_parent_id}' not found", "code": "NOT_FOUND"}
        if parent["project_id"] != project_id:
            conn.close()
            return 400, {"error": "Parent page belongs to a different project", "code": "VALIDATION_ERROR"}
        # Check for circular reference (new_parent cannot be a descendant)
        check_id = new_parent_id
        while check_id:
            check = conn.execute("SELECT parent_id FROM pages WHERE id = ?", (check_id,)).fetchone()
            if not check:
                break
            if check["parent_id"] == page_id:
                conn.close()
                return 400, {"error": "Cannot move page under its own descendant", "code": "VALIDATION_ERROR"}
            check_id = check["parent_id"]

    # Determine actual new parent (None if empty string or null)
    if new_parent_id == "" or new_parent_id is None:
        target_parent_id = None
    else:
        target_parent_id = new_parent_id

    parent_changed = (old_parent_id != target_parent_id)

    # Calculate new depth
    if parent_changed:
        if target_parent_id is None:
            new_depth = 0
        else:
            parent = conn.execute("SELECT depth FROM pages WHERE id = ?", (target_parent_id,)).fetchone()
            new_depth = parent["depth"] + 1
    else:
        new_depth = old_depth

    # Calculate position if not specified
    if new_position is None:
        pos_row = conn.execute(
            """SELECT MAX(position) as max_pos FROM pages
               WHERE project_id = ? AND parent_id IS ?""",
            (project_id, target_parent_id),
        ).fetchone()
        new_position = (pos_row["max_pos"] or 0) + 1
    else:
        new_position = float(new_position)

    # Update the page
    conn.execute(
        """UPDATE pages
           SET parent_id = ?, position = ?, depth = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (target_parent_id, new_position, new_depth, page_id),
    )

    # If parent changed, recursively update depth of all descendants
    if parent_changed:
        depth_delta = new_depth - old_depth
        if depth_delta != 0:
            # Use iterative approach to update all descendants
            conn.execute(
                """UPDATE pages SET depth = depth + ?,
                   updated_at = datetime('now')
                   WHERE id IN (
                       WITH RECURSIVE descendants AS (
                           SELECT id FROM pages WHERE parent_id = ?
                           UNION ALL
                           SELECT p.id FROM pages p
                           JOIN descendants d ON p.parent_id = d.id
                       )
                       SELECT id FROM descendants
                   )""",
                (depth_delta, page_id),
            )

    # If reordering within same parent, shift siblings
    if not parent_changed and new_position is not None:
        old_position = row["position"]
        if new_position < old_position:
            # Shift siblings at or after new_position up by 1
            conn.execute(
                """UPDATE pages SET position = position + 1,
                   updated_at = datetime('now')
                   WHERE project_id = ? AND parent_id IS ? AND position >= ? AND id != ?""",
                (project_id, target_parent_id, new_position, page_id),
            )
        elif new_position > old_position:
            # Shift siblings between old and new position down by 1
            conn.execute(
                """UPDATE pages SET position = position - 1,
                   updated_at = datetime('now')
                   WHERE project_id = ? AND parent_id IS ? AND position > ? AND position <= ? AND id != ?""",
                (project_id, target_parent_id, old_position, new_position, page_id),
            )

    detail = {"title": row["title"]}
    if parent_changed:
        detail["from_parent"] = old_parent_id
        detail["to_parent"] = target_parent_id
        detail["from_depth"] = old_depth
        detail["to_depth"] = new_depth
    detail["position"] = new_position

    _log_activity(conn, project_id, "page", page_id, "moved", actor, detail)

    conn.commit()

    updated = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    page = _page_row_to_dict(updated)
    conn.close()

    return 200, {"page": page}
