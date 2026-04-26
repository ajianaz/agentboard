"""api/analytics.py - Analytics and KPI endpoints.

Provides KPI metrics, trends, and analytics data for the dashboard.

Endpoints:
    GET /api/analytics/kpi        — KPI summary (all agents or filtered)
    GET /api/analytics/kpi/{id}   — KPI for a specific agent
    GET /api/analytics/trends     — trend data over time
    GET /api/analytics/agents     — agent performance cards
    GET /api/analytics/export     — export analytics as JSON/CSV
"""

import csv
import io
import json
from datetime import datetime, timedelta, timezone

from db import get_db
from kpi_engine import get_kpi_summary, get_kpi_engine
from api import router


@router.get("/api/analytics/kpi")
def get_kpi(params, query, body, headers):
    """Get KPI summary metrics.

    Query params:
        agent_id — filter by specific agent
        days     — lookback period (default 7, max 90)
        period   — 'daily' or 'weekly' (default 'daily')
    """
    try:
        days = min(int(query.get("days", ["7"])[0]), 90)
    except (ValueError, IndexError):
        days = 7
    if days < 1:
        days = 7

    agent_id = query.get("agent_id", [None])[0]
    period = query.get("period", ["daily"])[0]

    conn = get_db()

    if period == "weekly" and not agent_id:
        # Weekly summary for all agents
        weeks = min(max(days // 7, 1), 52)
        week_start = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
        rows = conn.execute(
            """SELECT k.*, a.name, a.role, a.avatar, a.color
               FROM kpi_weekly k
               LEFT JOIN agents a ON k.agent_id = a.id
               WHERE k.week_start >= ?
               ORDER BY k.week_start DESC, k.agent_id ASC""",
            (week_start,),
        ).fetchall()
        kpis = [dict(r) for r in rows]
    elif period == "weekly" and agent_id:
        weeks = min(max(days // 7, 1), 52)
        week_start = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
        rows = conn.execute(
            """SELECT k.*, a.name, a.role, a.avatar, a.color
               FROM kpi_weekly k
               LEFT JOIN agents a ON k.agent_id = a.id
               WHERE k.agent_id = ? AND k.week_start >= ?
               ORDER BY k.week_start DESC""",
            (agent_id, week_start),
        ).fetchall()
        kpis = [dict(r) for r in rows]
    else:
        # Daily KPI (default)
        summary = get_kpi_summary(conn, agent_id, days)
        conn.close()
        return 200, summary

    conn.close()
    return 200, {"kpis": kpis, "period": "weekly", "period_weeks": min(max(days // 7, 1), 52)}


@router.get("/api/analytics/kpi/{agent_id}")
def get_agent_kpi(params, query, body, headers):
    """Get KPI data for a specific agent.

    Path params:
        agent_id — agent ID

    Query params:
        days   — lookback period (default 7, max 90)
    """
    agent_id = params["agent_id"]
    try:
        days = min(int(query.get("days", ["7"])[0]), 90)
    except (ValueError, IndexError):
        days = 7

    conn = get_db()

    # Get agent info
    agent = conn.execute(
        "SELECT * FROM agents WHERE id = ?", (agent_id,)
    ).fetchone()

    if not agent:
        conn.close()
        return 404, {"error": "Agent not found", "code": "NOT_FOUND"}

    # Get KPI data
    summary = get_kpi_summary(conn, agent_id, days)

    # Add agent info
    summary["agent"] = {
        "id": agent["id"],
        "name": agent["name"],
        "role": agent["role"],
        "avatar": agent["avatar"],
        "color": agent["color"],
        "is_active": bool(agent["is_active"]),
    }

    conn.close()
    return 200, summary


@router.get("/api/analytics/trends")
def get_trends(params, query, body, headers):
    """Get trend data over time.

    Query params:
        metric — metric name (success_rate, tasks_completed, activity_count)
        days   — lookback period (default 30, max 90)
        agent_id — optional agent filter
    """
    metric = query.get("metric", ["success_rate"])[0]
    try:
        days = min(int(query.get("days", ["30"])[0]), 90)
    except (ValueError, IndexError):
        days = 30

    agent_id = query.get("agent_id", [None])[0]

    # Validate metric
    valid_metrics = {
        "success_rate": "success_rate",
        "tasks_completed": "tasks_completed",
        "tasks_created": "tasks_created",
        "activity_count": "activity_count",
        "avg_completion_hours": "avg_completion_hours",
        "comments_added": "comments_added",
    }
    col = valid_metrics.get(metric)
    if not col:
        return 400, {"error": f"Invalid metric. Valid: {', '.join(valid_metrics.keys())}", "code": "VALIDATION_ERROR"}

    date_start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_db()

    if agent_id:
        rows = conn.execute(
            f"""SELECT date, {col} as value, agent_id
                FROM kpi_daily
                WHERE agent_id = ? AND date >= ?
                ORDER BY date ASC""",
            (agent_id, date_start),
        ).fetchall()
    else:
        rows = conn.execute(
            f"""SELECT date, AVG({col}) as value, agent_id
                FROM kpi_daily
                WHERE date >= ?
                GROUP BY date
                ORDER BY date ASC""",
            (date_start,),
        ).fetchall()

    trends = [{"date": r["date"], "value": round(r["value"], 1) if r["value"] else 0} for r in rows]
    conn.close()

    return 200, {
        "metric": metric,
        "trends": trends,
        "period_days": days,
        "agent_id": agent_id,
    }


@router.get("/api/analytics/agents")
def get_agent_cards(params, query, body, headers):
    """Get performance cards for all agents.

    Query params:
        days — lookback period for KPI calculation (default 7)
    """
    try:
        days = min(int(query.get("days", ["7"])[0]), 90)
    except (ValueError, IndexError):
        days = 7

    conn = get_db()

    agents = conn.execute(
        "SELECT * FROM agents ORDER BY name ASC"
    ).fetchall()

    cards = []
    for agent in agents:
        summary = get_kpi_summary(conn, agent["id"], days)
        cards.append({
            "id": agent["id"],
            "name": agent["name"],
            "role": agent["role"],
            "avatar": agent["avatar"],
            "color": agent["color"],
            "is_active": bool(agent["is_active"]),
            "kpi": summary["summary"],
            "recent_activity": summary["kpis"][-3:] if summary["kpis"] else [],
        })

    conn.close()
    return 200, {"agents": cards, "period_days": days}


@router.get("/api/analytics/export")
def export_analytics(params, query, body, headers):
    """Export analytics data as JSON or CSV.

    Query params:
        format — 'json' or 'csv' (default 'json')
        days   — lookback period (default 7)
        type   — 'kpi' or 'activity' (default 'kpi')
    """
    export_format = query.get("format", ["json"])[0].lower()
    data_type = query.get("type", ["kpi"])[0].lower()

    try:
        days = min(int(query.get("days", ["7"])[0]), 90)
    except (ValueError, IndexError):
        days = 7

    conn = get_db()

    if data_type == "activity":
        date_start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        rows = conn.execute(
            """SELECT a.*, p.name as project_name, p.slug as project_slug
               FROM activity a
               LEFT JOIN projects p ON a.project_id = p.id
               WHERE a.created_at >= ?
               ORDER BY a.created_at DESC""",
            (date_start,),
        ).fetchall()
        data = [dict(r) for r in rows]
    else:
        date_start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = conn.execute(
            """SELECT k.*, a.name as agent_name, a.role as agent_role
               FROM kpi_daily k
               LEFT JOIN agents a ON k.agent_id = a.id
               WHERE k.date >= ?
               ORDER BY k.date DESC, k.agent_id ASC""",
            (date_start,),
        ).fetchall()
        data = [dict(r) for r in rows]

    conn.close()

    if export_format == "csv":
        if not data:
            return 200, {"error": "No data to export", "code": "EMPTY"}
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        csv_content = output.getvalue()
        return 200, {
            "format": "csv",
            "filename": f"agentboard_{data_type}_{days}d.csv",
            "content": csv_content,
            "rows": len(data),
        }

    return 200, {
        "format": "json",
        "type": data_type,
        "period_days": days,
        "data": data,
        "rows": len(data),
    }


@router.post("/api/analytics/recompute")
def recompute_kpi(params, query, body, headers):
    """Trigger immediate KPI recomputation.

    Useful after bulk imports or sample data generation.
    Requires authentication.
    """
    engine = get_kpi_engine()
    if not engine:
        return 503, {"error": "KPI engine not running", "code": "SERVICE_UNAVAILABLE"}

    try:
        engine.compute_daily()
        engine.compute_weekly()
        engine.cleanup()
    except Exception as e:
        return 500, {"error": f"KPI computation failed: {e}", "code": "INTERNAL_ERROR"}

    return 200, {"status": "recomputed", "message": "Daily and weekly KPIs recomputed"}
