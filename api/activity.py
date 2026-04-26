"""AgentBoard — Activity log endpoints.

Endpoints:
    GET /api/activity              — recent activity (all projects)
    GET /api/activity?project={slug}  — activity for specific project
    GET /api/activity?actor={agent_id} — activity by specific actor
    GET /api/activity/stats        — activity statistics summary
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
    """Return recent activity entries, optionally filtered.

    Query params:
        limit       — max rows to return (default 50, max 200)
        offset      — skip N rows (default 0)
        project     — filter by project slug
        actor       — filter by actor id
        target_type — filter by target type (task, page, comment, project, discussion)
        action      — filter by action (create, update, delete, etc.)
        since       — ISO timestamp lower bound (e.g. 2024-01-01T00:00:00Z)
        until       — ISO timestamp upper bound
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
    target_type = query.get("target_type", [None])[0]
    action = query.get("action", [None])[0]
    since = query.get("since", [None])[0]
    until = query.get("until", [None])[0]

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

    if target_type:
        conditions.append("a.target_type = ?")
        sql_params.append(target_type)

    if action:
        conditions.append("a.action = ?")
        sql_params.append(action)

    if since:
        conditions.append("a.created_at >= ?")
        sql_params.append(since)

    if until:
        conditions.append("a.created_at <= ?")
        sql_params.append(until)

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


@router.get("/api/activity/stats")
def activity_stats(params, query, body, headers):
    """Return activity statistics summary.

    Query params:
        days — lookback period in days (default 7, max 90)
    """
    try:
        days = min(int(query.get("days", ["7"])[0]), 90)
    except (ValueError, IndexError):
        days = 7

    conn = get_db()

    # Activity count by action type
    action_counts = conn.execute(
        """SELECT action, COUNT(*) as count
           FROM activity
           WHERE created_at >= datetime('now', ?)
           GROUP BY action
           ORDER BY count DESC""",
        (f"-{days} days",),
    ).fetchall()

    # Activity count by actor
    actor_counts = conn.execute(
        """SELECT actor, COUNT(*) as count
           FROM activity
           WHERE created_at >= datetime('now', ?)
           GROUP BY actor
           ORDER BY count DESC""",
        (f"-{days} days",),
    ).fetchall()

    # Activity count by day (last N days)
    daily_counts = conn.execute(
        """SELECT date(created_at) as day, COUNT(*) as count
           FROM activity
           WHERE created_at >= datetime('now', ?)
           GROUP BY day
           ORDER BY day DESC""",
        (f"-{days} days",),
    ).fetchall()

    # Total count
    total_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM activity WHERE created_at >= datetime('now', ?)",
        (f"-{days} days",),
    ).fetchone()

    conn.close()

    return 200, {
        "period_days": days,
        "total": total_row["cnt"],
        "by_action": [{"action": r["action"], "count": r["count"]} for r in action_counts],
        "by_actor": [{"actor": r["actor"], "count": r["count"]} for r in actor_counts],
        "by_day": [{"day": r["day"], "count": r["count"]} for r in daily_counts],
    }
