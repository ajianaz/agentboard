"""kpi_engine.py - KPI computation engine for AgentBoard.

Periodically calculates team performance metrics from activity data.
Uses batch writes to avoid SQLite contention.

Retention policy:
- Daily KPI: 90 days
- Weekly KPI: 365 days
- Activity log: 180 days

Usage:
    from kpi_engine import KPIEngine
    engine = KPIEngine()
    engine.compute_daily()   # Calculate today's metrics
    engine.compute_weekly()  # Aggregate weekly metrics
    engine.cleanup()         # Remove expired records
"""

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

from db import get_db

# Retention periods in days
RETENTION_DAILY_KPI = 90
RETENTION_WEEKLY_KPI = 365
RETENTION_ACTIVITY = 180

# Module-level singleton reference (set by server.py on startup)
_engine = None


def get_kpi_engine():
    """Return the running KPIEngine instance, or None if not started."""
    return _engine


def set_kpi_engine(engine):
    """Set the module-level KPIEngine reference (called by server.py)."""
    global _engine
    _engine = engine


class KPIEngine:
    """Background KPI computation engine with batch writes."""

    def __init__(self, interval_seconds: int = 300):
        """Initialize the KPI engine.

        Args:
            interval_seconds: How often to compute KPIs (default: 5 minutes).
        """
        self.interval = interval_seconds
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        """Start the background KPI computation thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="kpi-engine")
        self._thread.start()

    def stop(self):
        """Signal the background thread to stop."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _run_loop(self):
        """Main loop: compute KPIs and cleanup at regular intervals."""
        while not self._stop_event.is_set():
            try:
                self.compute_daily()
                self.compute_weekly()
                self.cleanup()
            except Exception as e:
                import sys
                sys.stderr.write(f"[KPI Engine] Error: {e}\n")
            # Wait for next interval or until stopped
            self._stop_event.wait(timeout=self.interval)

    def compute_daily(self):
        """Compute daily KPI metrics for all agents.

        For each agent and each day with activity, calculate:
        - tasks_created, tasks_completed, tasks_moved_to_review
        - comments_added, success_rate, avg_completion_hours
        - activity_count
        """
        conn = get_db()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Get all active agents
        agents = conn.execute(
            "SELECT id FROM agents WHERE is_active = 1"
        ).fetchall()

        if not agents:
            conn.close()
            return

        # Compute KPIs for each agent for the last 2 days (to catch late entries)
        for days_ago in [0, 1]:
            date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            # Match activity.created_at format: "YYYY-MM-DD HH:MM:SS"
            date_start = f"{date} 00:00:00"
            date_end = f"{date} 23:59:59"

            for agent in agents:
                agent_id = agent["id"]
                self._compute_agent_daily(conn, agent_id, date, date_start, date_end)

        conn.commit()
        conn.close()

    def _compute_agent_daily(self, conn: sqlite3.Connection, agent_id: str,
                              date: str, date_start: str, date_end: str):
        """Compute and upsert daily KPI for a single agent."""
        # Tasks created
        tasks_created = conn.execute(
            """SELECT COUNT(*) as c FROM activity
               WHERE actor = ? AND action = 'created' AND target_type = 'task'
               AND created_at >= ? AND created_at <= ?""",
            (agent_id, date_start, date_end),
        ).fetchone()["c"]

        # Tasks completed (status changed to done)
        # Match detail JSON: {"from": "todo", "to": "done"}
        tasks_completed = conn.execute(
            """SELECT COUNT(*) as c FROM activity
               WHERE actor = ? AND target_type = 'task'
               AND action = 'status changed'
               AND detail LIKE ? AND created_at >= ? AND created_at <= ?""",
            (agent_id, '%"to": "done"%', date_start, date_end),
        ).fetchone()["c"]

        # Tasks moved to review
        tasks_review = conn.execute(
            """SELECT COUNT(*) as c FROM activity
               WHERE actor = ? AND target_type = 'task'
               AND action = 'status changed'
               AND detail LIKE ? AND created_at >= ? AND created_at <= ?""",
            (agent_id, '%"to": "review"%', date_start, date_end),
        ).fetchone()["c"]

        # Comments added
        comments = conn.execute(
            """SELECT COUNT(*) as c FROM activity
               WHERE actor = ? AND action = 'created' AND target_type = 'comment'
               AND created_at >= ? AND created_at <= ?""",
            (agent_id, date_start, date_end),
        ).fetchone()["c"]

        # Total activity count
        activity_count = conn.execute(
            """SELECT COUNT(*) as c FROM activity
               WHERE actor = ?
               AND created_at >= ? AND created_at <= ?""",
            (agent_id, date_start, date_end),
        ).fetchone()["c"]

        # Success rate: completed / max(created, 1) — how many created tasks got done
        success_rate = round(tasks_completed / max(tasks_created, 1) * 100, 1) if tasks_created > 0 else 0.0

        # Average completion time (hours) — from task started_at to completed_at
        avg_hours = conn.execute(
            """SELECT AVG(
                (julianday(replace(completed_at, 'Z', '')) -
                 julianday(replace(started_at, 'Z', ''))) * 24
               ) as avg_h
               FROM tasks
               WHERE assignee = ? AND status = 'done'
               AND completed_at >= ? AND completed_at <= ?
               AND started_at IS NOT NULL AND started_at != ''""",
            (agent_id, date_start, date_end),
        ).fetchone()["avg_h"]
        avg_hours = round(avg_hours, 1) if avg_hours else 0.0

        # Upsert into kpi_daily
        conn.execute(
            """INSERT INTO kpi_daily (agent_id, date, tasks_created, tasks_completed,
               tasks_moved_to_review, comments_added, success_rate, avg_completion_hours, activity_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(agent_id, date) DO UPDATE SET
               tasks_created = excluded.tasks_created,
               tasks_completed = excluded.tasks_completed,
               tasks_moved_to_review = excluded.tasks_moved_to_review,
               comments_added = excluded.comments_added,
               success_rate = excluded.success_rate,
               avg_completion_hours = excluded.avg_completion_hours,
               activity_count = excluded.activity_count""",
            (agent_id, date, tasks_created, tasks_completed, tasks_review,
             comments, success_rate, avg_hours, activity_count),
        )

    def compute_weekly(self):
        """Aggregate daily KPIs into weekly summaries."""
        conn = get_db()

        # Only compute for the current week and last week
        for weeks_ago in [0, 1]:
            week_start = (datetime.now(timezone.utc) - timedelta(weeks=weeks_ago, days=datetime.now(timezone.utc).weekday())).strftime("%Y-%m-%d")
            week_end = (datetime.now(timezone.utc) - timedelta(weeks=weeks_ago, days=datetime.now(timezone.utc).weekday() - 6)).strftime("%Y-%m-%d")

            # Get distinct agents from daily KPIs in this week
            agents = conn.execute(
                """SELECT DISTINCT agent_id FROM kpi_daily
                   WHERE date >= ? AND date <= ?""",
                (week_start, week_end),
            ).fetchall()

            for agent in agents:
                agent_id = agent["agent_id"]
                row = conn.execute(
                    """SELECT
                        SUM(tasks_created) as tasks_created,
                        SUM(tasks_completed) as tasks_completed,
                        AVG(success_rate) as success_rate,
                        AVG(avg_completion_hours) as avg_completion_hours,
                        SUM(activity_count) as activity_count
                       FROM kpi_daily
                       WHERE agent_id = ? AND date >= ? AND date <= ?""",
                    (agent_id, week_start, week_end),
                ).fetchone()

                conn.execute(
                    """INSERT INTO kpi_weekly (agent_id, week_start, tasks_created, tasks_completed,
                       success_rate, avg_completion_hours, activity_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(agent_id, week_start) DO UPDATE SET
                       tasks_created = excluded.tasks_created,
                       tasks_completed = excluded.tasks_completed,
                       success_rate = excluded.success_rate,
                       avg_completion_hours = excluded.avg_completion_hours,
                       activity_count = excluded.activity_count""",
                    (agent_id, week_start,
                     row["tasks_created"] or 0,
                     row["tasks_completed"] or 0,
                     round(row["success_rate"] or 0, 1),
                     round(row["avg_completion_hours"] or 0, 1),
                     row["activity_count"] or 0),
                )

        conn.commit()
        conn.close()

    def cleanup(self):
        """Remove expired KPI and activity records based on retention policy."""
        conn = get_db()
        now = datetime.now(timezone.utc)

        # Daily KPI: 90 days
        daily_cutoff = (now - timedelta(days=RETENTION_DAILY_KPI)).strftime("%Y-%m-%d")
        deleted = conn.execute(
            "DELETE FROM kpi_daily WHERE date < ?", (daily_cutoff,)
        ).rowcount
        if deleted:
            import sys
            sys.stderr.write(f"[KPI Engine] Cleaned {deleted} expired daily KPI records\n")

        # Weekly KPI: 365 days
        weekly_cutoff = (now - timedelta(days=RETENTION_WEEKLY_KPI)).strftime("%Y-%m-%d")
        deleted = conn.execute(
            "DELETE FROM kpi_weekly WHERE week_start < ?", (weekly_cutoff,)
        ).rowcount
        if deleted:
            import sys
            sys.stderr.write(f"[KPI Engine] Cleaned {deleted} expired weekly KPI records\n")

        # Activity log: 180 days
        activity_cutoff = (now - timedelta(days=RETENTION_ACTIVITY)).strftime("%Y-%m-%dT00:00:00Z")
        deleted = conn.execute(
            "DELETE FROM activity WHERE created_at < ?", (activity_cutoff,)
        ).rowcount
        if deleted:
            import sys
            sys.stderr.write(f"[KPI Engine] Cleaned {deleted} expired activity records\n")

        conn.commit()
        conn.close()

    def compute_now(self):
        """Compute KPIs immediately (for testing and on-demand)."""
        self.compute_daily()
        self.compute_weekly()


def get_kpi_summary(conn: sqlite3.Connection, agent_id: str | None = None,
                     days: int = 7) -> dict:
    """Get KPI summary for display.

    Args:
        conn: Database connection
        agent_id: Optional agent ID filter
        days: Number of days to look back

    Returns:
        Dict with daily KPIs and summary stats.
    """
    date_start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    if agent_id:
        rows = conn.execute(
            """SELECT * FROM kpi_daily
               WHERE agent_id = ? AND date >= ?
               ORDER BY date ASC""",
            (agent_id, date_start),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM kpi_daily
               WHERE date >= ?
               ORDER BY date ASC, agent_id ASC""",
            (date_start,),
        ).fetchall()

    kpis = [dict(r) for r in rows]

    # Aggregate summary
    summary = {
        "total_tasks_created": sum(k.get("tasks_created", 0) for k in kpis),
        "total_tasks_completed": sum(k.get("tasks_completed", 0) for k in kpis),
        "avg_success_rate": round(
            sum(k.get("success_rate", 0) for k in kpis) / max(len(kpis), 1), 1
        ),
        "avg_completion_hours": round(
            sum(k.get("avg_completion_hours", 0) for k in kpis) / max(len(kpis), 1), 1
        ),
        "total_activity": sum(k.get("activity_count", 0) for k in kpis),
        "days": len(set(k.get("date") for k in kpis)),
    }

    return {"kpis": kpis, "summary": summary, "period_days": days}
