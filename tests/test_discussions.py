"""Tests for discussion system."""

import os
import sqlite3
import sys

import pytest

sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from db import FULL_SCHEMA_SQL, gen_id


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(FULL_SCHEMA_SQL)
    return conn


class TestDiscussions:
    def _create_discussion(self, db, title="Test Discussion", max_rounds=3):
        disc_id = gen_id()
        db.execute(
            "INSERT INTO discussions (id, title, status, current_round, max_rounds, created_by, created_at, updated_at) VALUES (?, ?, 'open', 1, ?, 'tester', datetime('now'), datetime('now'))",
            (disc_id, title, max_rounds),
        )
        db.commit()
        return disc_id

    def _add_feedback(self, db, disc_id, participant="agent1", verdict="approve", content="LGTM", round_num=1):
        fb_id = gen_id()
        db.execute(
            "INSERT INTO discussion_feedback (id, discussion_id, participant, role, verdict, content, round, created_at) VALUES (?, ?, ?, 'Agent', ?, ?, ?, datetime('now'))",
            (fb_id, disc_id, participant, verdict, content, round_num),
        )
        db.commit()
        return fb_id

    def test_create_discussion(self, db):
        disc_id = self._create_discussion(db)
        row = db.execute("SELECT * FROM discussions WHERE id = ?", (disc_id,)).fetchone()
        assert row is not None
        assert row["title"] == "Test Discussion"
        assert row["status"] == "open"

    def test_add_feedback(self, db):
        disc_id = self._create_discussion(db)
        fb_id = self._add_feedback(db, disc_id)
        row = db.execute("SELECT * FROM discussion_feedback WHERE id = ?", (fb_id,)).fetchone()
        assert row is not None
        assert row["participant"] == "agent1"
        assert row["verdict"] == "approve"

    def test_multiple_feedback(self, db):
        disc_id = self._create_discussion(db, max_rounds=3)
        for p, v in [("a1", "approve"), ("a2", "conditional"), ("a3", "reject")]:
            self._add_feedback(db, disc_id, participant=p, verdict=v)
        count = db.execute("SELECT COUNT(*) FROM discussion_feedback WHERE discussion_id = ?", (disc_id,)).fetchone()[0]
        assert count == 3

    def test_close_discussion(self, db):
        disc_id = self._create_discussion(db)
        db.execute("UPDATE discussions SET status = 'closed' WHERE id = ?", (disc_id,))
        db.commit()
        row = db.execute("SELECT * FROM discussions WHERE id = ?", (disc_id,)).fetchone()
        assert row["status"] == "closed"

    def test_consensus_status(self, db):
        disc_id = self._create_discussion(db)
        db.execute("UPDATE discussions SET status = 'consensus' WHERE id = ?", (disc_id,))
        db.commit()
        row = db.execute("SELECT * FROM discussions WHERE id = ?", (disc_id,)).fetchone()
        assert row["status"] == "consensus"
