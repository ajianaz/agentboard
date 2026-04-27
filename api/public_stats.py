"""api/public_stats.py — Public-safe aggregated metrics.

Returns only aggregate counts and summaries — no task titles,
descriptions, agent config, or raw activity content.

Endpoint:
    GET /api/stats/public — aggregated safe metrics for unauthenticated visitors
"""

from db import get_db
from api import router, is_authenticated


@router.get("/api/stats/public")
def get_public_stats(params, query, body, headers):
    """Public-safe stats: only aggregated counts, no sensitive data.

    Returns:
        agents:          [{name, done, in_progress, proposed}]
        projects:        [{name, slug, icon, total, done, completion_pct}]
        status_totals:   {todo: N, proposed: N, in_progress: N, review: N, done: N}
        recent_activity: {last_7_days: N, last_30_days: N}
    """
    conn = get_db()
    authed = is_authenticated(headers)

    # --- Per-agent task counts (only non-archived, respect visibility for unauth) ---
    vis_filter = "" if authed else "AND p.visibility = 'public'"
    agent_rows = conn.execute(
        f"""SELECT t.assignee,
                  COUNT(t.id) as total,
                  SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done,
                  SUM(CASE WHEN t.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                  SUM(CASE WHEN t.status = 'proposed' THEN 1 ELSE 0 END) as proposed,
                  SUM(CASE WHEN t.status = 'review' THEN 1 ELSE 0 END) as review
           FROM tasks t
           JOIN projects p ON t.project_id = p.id
           WHERE p.is_archived = 0 {vis_filter} AND t.assignee IS NOT NULL AND t.assignee != ''
           GROUP BY t.assignee
           ORDER BY done DESC"""
    ).fetchall()

    agents = []
    for r in agent_rows:
        total = r["total"] or 0
        done = r["done"] or 0
        agents.append({
            "name": r["assignee"],
            "total": total,
            "done": done,
            "in_progress": r["in_progress"] or 0,
            "proposed": r["proposed"] or 0,
            "review": r["review"] or 0,
            "completion_pct": round(done / total * 100, 1) if total > 0 else 0,
        })

    # --- Per-project breakdown (respect visibility for unauth) ---
    vis_filter = "" if authed else "AND p.visibility = 'public'"
    project_rows = conn.execute(
        f"""SELECT p.name, p.slug, p.icon, p.color,
                  COUNT(t.id) as total_tasks,
                  SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done_tasks,
                  SUM(CASE WHEN t.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tasks,
                  SUM(CASE WHEN t.status = 'proposed' THEN 1 ELSE 0 END) as proposed_tasks
           FROM projects p
           LEFT JOIN tasks t ON t.project_id = p.id
           WHERE p.is_archived = 0 {vis_filter}
           GROUP BY p.id
           ORDER BY p.position ASC"""
    ).fetchall()

    projects = []
    for r in project_rows:
        total = r["total_tasks"] or 0
        done = r["done_tasks"] or 0
        projects.append({
            "name": r["name"],
            "slug": r["slug"],
            "icon": r["icon"],
            "color": r["color"],
            "total": total,
            "done": done,
            "in_progress": r["in_progress_tasks"] or 0,
            "proposed": r["proposed_tasks"] or 0,
            "completion_pct": round(done / total * 100, 1) if total > 0 else 0,
        })

    # --- Overall status totals (non-archived, respect visibility for unauth) ---
    totals = conn.execute(
        f"""SELECT
              SUM(CASE WHEN t.status = 'proposed' THEN 1 ELSE 0 END) as proposed,
              SUM(CASE WHEN t.status = 'todo' THEN 1 ELSE 0 END) as todo,
              SUM(CASE WHEN t.status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
              SUM(CASE WHEN t.status = 'review' THEN 1 ELSE 0 END) as review,
              SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as done,
              COUNT(t.id) as total
           FROM tasks t
           JOIN projects p ON t.project_id = p.id
           WHERE p.is_archived = 0 {vis_filter}"""
    ).fetchone()

    status_totals = {
        "total": totals["total"] or 0,
        "proposed": totals["proposed"] or 0,
        "todo": totals["todo"] or 0,
        "in_progress": totals["in_progress"] or 0,
        "review": totals["review"] or 0,
        "done": totals["done"] or 0,
    }

    # --- Recent activity counts (safe: just counts, no content) ---
    activity_7d = conn.execute(
        "SELECT COUNT(*) as cnt FROM activity WHERE created_at >= datetime('now', '-7 days')"
    ).fetchone()
    activity_30d = conn.execute(
        "SELECT COUNT(*) as cnt FROM activity WHERE created_at >= datetime('now', '-30 days')"
    ).fetchone()

    recent_activity = {
        "last_7_days": activity_7d["cnt"] or 0,
        "last_30_days": activity_30d["cnt"] or 0,
    }

    conn.close()

    return 200, {
        "agents": agents,
        "projects": projects,
        "status_totals": status_totals,
        "recent_activity": recent_activity,
    }
