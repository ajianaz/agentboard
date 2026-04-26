"""Tests for KPI computation engine."""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from db import FULL_SCHEMA_SQL, gen_id
from kpi_engine import KPIEngine, get_kpi_engine, set_kpi_engine, get_kpi_summary, RETENTION_DAILY_KPI


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(FULL_SCHEMA_SQL)
    return conn


@pytest.fixture
def sample_agents(db):
    agents = [
        ("alice", "Alice", "Developer", "👩‍💻", "#3b82f6"),
        ("bob", "Bob", "Designer", "👨‍🎨", "#8b5cf6"),
    ]
    for agent_id, name, role, avatar, color in agents:
        db.execute(
            "INSERT INTO agents (id, name, role, avatar, color, is_active) VALUES (?, ?, ?, ?, ?, 1)",
            (agent_id, name, role, avatar, color),
        )
    db.commit()
    return [a[0] for a in agents]


@pytest.fixture
def kpi_populated_db(db, sample_agents):
    """DB with agents and pre-computed KPI data (no engine needed)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    for agent_id, tasks_cr, tasks_done, sr, ach, act in [
        ("alice", 5, 4, 80.0, 3.5, 12),
        ("bob", 3, 2, 66.7, 5.0, 8),
    ]:
        for date in [today, yesterday]:
            db.execute(
                "INSERT INTO kpi_daily (agent_id, date, tasks_created, tasks_completed, success_rate, avg_completion_hours, activity_count) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (agent_id, date, tasks_cr, tasks_done, sr, ach, act),
            )
    db.commit()
    return db


class TestKPIEngine:
    def test_engine_creation(self):
        engine = KPIEngine(interval_seconds=1)
        assert engine.interval == 1

    def test_singleton_pattern(self):
        engine = KPIEngine(interval_seconds=1)
        set_kpi_engine(engine)
        assert get_kpi_engine() is engine
        set_kpi_engine(None)
        assert get_kpi_engine() is None

    def test_get_kpi_summary_structure(self, kpi_populated_db):
        result = get_kpi_summary(kpi_populated_db, "alice", 7)
        assert "kpis" in result
        assert "summary" in result
        assert isinstance(result["kpis"], list)
        assert len(result["kpis"]) >= 1

    def test_get_kpi_summary_all_agents(self, kpi_populated_db):
        result = get_kpi_summary(kpi_populated_db, None, 7)
        assert result["summary"]["total_tasks_created"] >= 16  # 2 agents * 2 days

    def test_get_kpi_summary_single_agent(self, kpi_populated_db):
        result = get_kpi_summary(kpi_populated_db, "alice", 7)
        assert result["summary"]["total_tasks_created"] == 10  # 5 * 2 days

    def test_retention_cleanup_sql(self, db, sample_agents):
        """Test retention cleanup SQL logic directly."""
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d")
        recent_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO kpi_daily (agent_id, date, tasks_created, tasks_completed, success_rate, avg_completion_hours, activity_count) VALUES (?, ?, 1, 1, 100.0, 2.0, 3)",
            ("alice", old_date),
        )
        db.execute(
            "INSERT INTO kpi_daily (agent_id, date, tasks_created, tasks_completed, success_rate, avg_completion_hours, activity_count) VALUES (?, ?, 2, 1, 50.0, 4.0, 5)",
            ("bob", recent_date),
        )
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM kpi_daily").fetchone()[0] == 2
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAILY_KPI)).strftime("%Y-%m-%d")
        db.execute("DELETE FROM kpi_daily WHERE date < ?", (cutoff,))
        db.commit()
        assert db.execute("SELECT COUNT(*) FROM kpi_daily WHERE date = ?", (old_date,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM kpi_daily WHERE date = ?", (recent_date,)).fetchone()[0] == 1
