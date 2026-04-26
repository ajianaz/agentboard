"""AgentBoard — Activity log endpoints.

Endpoints:
    GET /api/activity              — recent activity (all projects)
    GET /api/activity?project={slug}  — activity for specific project
    GET /api/activity?actor={agent_id} — activity by specific actor
"""

import json
from db import get_db
from api import router


def _activity_row_to_dict(row) -> dict:
    """Convert an activity Row (with joined project_name) to a plain dict."""
    d = dict(row)
    # Parse JSON detail field
    raw = d.get("detail")
    if isinstance(raw, str):
        try:
            d["detail"] = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            d["detail"] = {}
    return d


@router.get("/api/activity")
def list_activity(params, query, body, headers):
    """Return recent activity entries, optionally filtered by project or actor.

    Query params:
        limit   — max rows to return (default 50, max 200)
        offset  — skip N rows (default 0)
        project — filter by project slug
        actor   — filter by actor id
    """
    # Parse pagination
    try:
        limit = min(int(query.get("limit", ["50"])[0]), 200)
    except (ValueError, IndexError):
        limit = 50
    if limit < 1:
        limit = 50

    try:
        offset = max(int(query.get("offset", ["0"])[0]), 0)
    except (ValueError, IndexError):
        offset = 0

    # Parse optional filters
    project_slug = query.get("project", [None])[0]
    actor = query.get("actor", [None])[0]

    conn = get_db()

    # Build query with optional filters
    conditions = []
    sql_params = []

    if project_slug:
        conditions.append("p.slug = ?")
        sql_params.append(project_slug)

    if actor:
        conditions.append("a.actor = ?")
        sql_params.append(actor)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    rows = conn.execute(
        f"""SELECT a.id, a.project_id, a.target_type, a.target_id,
                   a.action, a.actor, a.detail, a.created_at,
                   p.name as project_name, p.slug as project_slug
            FROM activity a
            LEFT JOIN projects p ON a.project_id = p.id
            {where_clause}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?""",
        (*sql_params, limit, offset),
    ).fetchall()

    # Total count (for pagination)
    count_rows = conn.execute(
        f"SELECT COUNT(*) as cnt FROM activity a LEFT JOIN projects p ON a.project_id = p.id {where_clause}",
        (*sql_params,),
    ).fetchone()
    total = count_rows["cnt"]

    activities = [_activity_row_to_dict(r) for r in rows]
    conn.close()

    return 200, {
        "activity": activities,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
