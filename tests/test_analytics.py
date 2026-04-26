"""Tests for analytics module."""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from db import FULL_SCHEMA_SQL, gen_id
from kpi_engine import get_kpi_summary


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(FULL_SCHEMA_SQL)
    return conn


@pytest.fixture
def populated_db(db):
    """DB with agents and pre-computed KPI data (engine writes to global DB, so we insert directly)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    for agent_id, tasks_cr, tasks_done, sr, ach, act in [
        ("alice", 5, 4, 80.0, 3.5, 12),
        ("bob", 3, 2, 66.7, 5.0, 8),
    ]:
        db.execute(
            "INSERT INTO agents (id, name, role, avatar, color, is_active) VALUES (?, ?, 'Dev', '🤖', '#fff', 1)",
            (agent_id, agent_id.capitalize()),
        )
        for date in [today, yesterday]:
            db.execute(
                "INSERT INTO kpi_daily (agent_id, date, tasks_created, tasks_completed, success_rate, avg_completion_hours, activity_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agent_id, date, tasks_cr, tasks_done, sr, ach, act),
            )
    db.commit()
    return db


class TestAnalytics:
    def test_get_kpi_summary_all_agents(self, populated_db):
        result = get_kpi_summary(populated_db, None, 7)
        assert "summary" in result
        assert "kpis" in result
        assert result["summary"]["total_tasks_created"] >= 16

    def test_get_kpi_summary_single_agent(self, populated_db):
        result = get_kpi_summary(populated_db, "alice", 7)
        assert "summary" in result
        assert result["summary"]["total_tasks_created"] == 10

    def test_kpi_daily_rows_exist(self, populated_db):
        rows = populated_db.execute("SELECT COUNT(*) FROM kpi_daily").fetchone()[0]
        assert rows >= 4  # 2 agents * 2 days

    def test_trends_data(self, populated_db):
        rows = populated_db.execute("SELECT date, success_rate FROM kpi_daily ORDER BY date").fetchall()
        assert len(rows) >= 2
        for row in rows:
            assert row["date"] is not None
