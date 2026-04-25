"""Tests for AgentBoard database module."""

import os
import sqlite3
import sys

import pytest

# Ensure we can import from project root
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestDatabase:
    """Test db.py — schema, migrations, helpers."""

    def test_schema_creates_all_tables(self, db_conn):
        """Full schema should create all expected tables."""
        tables = [row[0] for row in db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
        expected = ["projects", "tasks", "pages", "agents", "comments", "activity"]
        for t in expected:
            assert t in tables, f"Missing table: {t}"

    def test_projects_table_structure(self, db_conn):
        """Projects table should have expected columns."""
        columns = [col[1] for col in db_conn.execute("PRAGMA table_info(projects)").fetchall()]
        for col in ["id", "name", "slug", "description", "is_archived"]:
            assert col in columns, f"Missing column: {col}"

    def test_tasks_table_structure(self, db_conn):
        """Tasks table should have expected columns."""
        columns = [col[1] for col in db_conn.execute("PRAGMA table_info(tasks)").fetchall()]
        for col in ["id", "project_id", "title", "status", "priority", "assignee"]:
            assert col in columns, f"Missing column: {col}"

    def test_pages_table_structure(self, db_conn):
        """Pages table should have expected columns."""
        columns = [col[1] for col in db_conn.execute("PRAGMA table_info(pages)").fetchall()]
        for col in ["id", "project_id", "parent_id", "title", "content"]:
            assert col in columns, f"Missing column: {col}"

    def test_agents_table_structure(self, db_conn):
        """Agents table should have expected columns."""
        columns = [col[1] for col in db_conn.execute("PRAGMA table_info(agents)").fetchall()]
        for col in ["id", "name", "role", "avatar", "is_active"]:
            assert col in columns, f"Missing column: {col}"

    def test_fts5_virtual_table(self, db_conn):
        """FTS5 search table should exist."""
        tables = [row[0] for row in db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        fts_tables = [t for t in tables if "search" in t or "fts" in t]
        assert len(fts_tables) > 0, "FTS5 virtual table not found"

    def test_gen_id_produces_unique_ids(self):
        """gen_id should produce unique hex strings."""
        from db import gen_id
        ids = [gen_id() for _ in range(100)]
        assert len(set(ids)) == 100, "gen_id produced duplicate IDs"
        assert all(len(i) == 16 for i in ids), "gen_id should produce 16-char hex strings"
