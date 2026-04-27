"""Tests for discussion system."""

import json
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
    # Ensure v6 columns exist (added by ALTER TABLE in migration)
    try:
        conn.execute("ALTER TABLE discussions ADD COLUMN context TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists
    try:
        conn.execute("ALTER TABLE discussions ADD COLUMN participants TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE discussions ADD COLUMN leader TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
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


class TestDiscussionWebhooks:
    """Test webhook helpers for discussion events."""

    def _create_discussion(self, db, title="Webhook Test", participants=None, leader=""):
        disc_id = gen_id()
        parts_json = json.dumps(participants or []) if participants else "[]"
        db.execute(
            """INSERT INTO discussions (id, title, status, current_round, max_rounds,
               created_by, created_at, updated_at, participants, leader)
               VALUES (?, ?, 'open', 1, 3, 'tester', datetime('now'), datetime('now'), ?, ?)""",
            (disc_id, title, parts_json, leader),
        )
        db.commit()
        row = db.execute("SELECT * FROM discussions WHERE id = ?", (disc_id,)).fetchone()
        return dict(row)

    def test_on_discussion_created_notifies_participants(self, db):
        """on_discussion_created should call notify_agent for each participant."""
        from unittest.mock import patch
        discussion = self._create_discussion(
            db, participants=["alpha", "beta", "gamma"], leader="alpha"
        )
        with patch("webhook.notify_agent") as mock_notify:
            from webhook import on_discussion_created
            on_discussion_created(discussion, "alpha")
            # Should notify beta and gamma (not alpha who is the creator)
            assert mock_notify.call_count == 2
            targets = {call.args[0] for call in mock_notify.call_args_list}
            assert targets == {"beta", "gamma"}
            # Check event type
            for call in mock_notify.call_args_list:
                assert call.args[1] == "discussion.created"

    def test_on_discussion_feedback_notifies_leader(self, db):
        """on_discussion_feedback should notify leader and other participants."""
        from unittest.mock import patch
        discussion = self._create_discussion(
            db, participants=["alpha", "beta"], leader="alpha"
        )
        feedback = {"participant": "beta", "verdict": "approve", "content": "LGTM", "round": 1}
        with patch("webhook.notify_agent") as mock_notify:
            from webhook import on_discussion_feedback
            on_discussion_feedback(discussion, feedback, "beta")
            # Should notify alpha (leader) — not beta (the feedback author)
            assert mock_notify.call_count == 1
            assert mock_notify.call_args[0][0] == "alpha"
            assert mock_notify.call_args[0][1] == "discussion.feedback"

    def test_on_discussion_closed_notifies_all(self, db):
        """on_discussion_closed should notify all participants."""
        from unittest.mock import patch
        discussion = self._create_discussion(
            db, participants=["alpha", "beta", "gamma"], leader="alpha"
        )
        discussion["status"] = "consensus"
        with patch("webhook.notify_agent") as mock_notify:
            from webhook import on_discussion_closed
            on_discussion_closed(discussion, "alpha")
            # Should notify all participants (including closer)
            assert mock_notify.call_count == 3
            for call in mock_notify.call_args_list:
                assert call.args[1] == "discussion.closed"

    def test_on_discussion_created_dict_participants(self, db):
        """Participants as list of dicts (id/name) should be handled."""
        from unittest.mock import patch
        discussion = self._create_discussion(
            db,
            participants=[{"id": "alpha"}, {"name": "beta"}],
            leader="alpha",
        )
        with patch("webhook.notify_agent") as mock_notify:
            from webhook import on_discussion_created
            on_discussion_created(discussion, "some_other_agent")
            targets = {call.args[0] for call in mock_notify.call_args_list}
            assert "alpha" in targets
            assert "beta" in targets

    def test_on_discussion_created_no_participants(self, db):
        """No crash when participants list is empty."""
        from unittest.mock import patch
        discussion = self._create_discussion(db, participants=[])
        with patch("webhook.notify_agent") as mock_notify:
            from webhook import on_discussion_created
            on_discussion_created(discussion, "tester")
            assert mock_notify.call_count == 0
