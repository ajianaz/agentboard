"""Pytest fixtures for AgentBoard tests.

Provides:
- db_conn: Fresh in-memory SQLite connection with full schema
- api_key: Tuple of (raw_key, hashed_key) for testing
- sample_project: Pre-created test project in the db_conn
"""

import os
import sqlite3

import pytest

# Ensure we can import from project root
sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)


@pytest.fixture
def db_conn():
    """Provide a fresh in-memory SQLite connection with full schema."""
    from db import SCHEMA_SQL

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def api_key():
    """Provide a test API key as (raw_key, hashed_key) tuple."""
    from auth import hash_key

    raw = "ab_test_key_for_unit_tests"
    return raw, hash_key(raw)


@pytest.fixture
def sample_project(db_conn):
    """Create a sample project for testing.

    Depends on db_conn — the project lives in the same in-memory database
    that the test is using.
    """
    from db import gen_id

    project_id = gen_id()
    db_conn.execute(
        "INSERT INTO projects (id, name, slug) VALUES (?, ?, ?)",
        (project_id, "Test Project", "test-project"),
    )
    db_conn.commit()
    return {"id": project_id, "name": "Test Project", "slug": "test-project"}
