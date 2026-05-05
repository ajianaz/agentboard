"""Tests for plan validation completeness check."""

import os
import json
import sqlite3

import pytest

sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)

from api.plans import _validate_plan_for_approval
from db import gen_id


class TestPlanValidationCompleteness:
    """Test _validate_plan_for_approval returns correct warnings."""

    def test_perfect_plan_no_warnings(self):
        plan = {
            "description": "Build the thing",
            "steps": [{"title": "Design"}, {"title": "Implement"}, {"title": "Test"}],
            "assignee": "kai",
        }
        assert _validate_plan_for_approval(plan) == []

    def test_no_description(self):
        plan = {
            "description": "",
            "steps": [{"title": "Step 1"}],
            "assignee": "kai",
        }
        warnings = _validate_plan_for_approval(plan)
        assert any("description" in w.lower() for w in warnings)

    def test_no_steps(self):
        plan = {
            "description": "A plan",
            "steps": [],
            "assignee": "kai",
        }
        warnings = _validate_plan_for_approval(plan)
        assert any("steps" in w.lower() for w in warnings)

    def test_step_without_title(self):
        plan = {
            "description": "A plan",
            "steps": [{"title": "Good step"}, {"title": ""}, {"description": "No title step"}],
            "assignee": "kai",
        }
        warnings = _validate_plan_for_approval(plan)
        step_warnings = [w for w in warnings if "step" in w.lower()]
        assert len(step_warnings) >= 1

    def test_no_assignee(self):
        plan = {
            "description": "A plan",
            "steps": [{"title": "Step 1"}],
            "assignee": "",
        }
        warnings = _validate_plan_for_approval(plan)
        assert any("assignee" in w.lower() for w in warnings)

    def test_steps_as_json_string(self):
        """Steps stored as JSON string should be parsed correctly."""
        plan = {
            "description": "A plan",
            "steps": json.dumps([{"title": "Step 1"}]),
            "assignee": "kai",
        }
        assert _validate_plan_for_approval(plan) == []

    def test_invalid_steps_json_string(self):
        """Invalid JSON string for steps should be treated as empty."""
        plan = {
            "description": "A plan",
            "steps": "not json",
            "assignee": "kai",
        }
        warnings = _validate_plan_for_approval(plan)
        assert any("steps" in w.lower() for w in warnings)

    def test_all_issues_at_once(self):
        plan = {
            "description": "",
            "steps": [],
            "assignee": "",
        }
        warnings = _validate_plan_for_approval(plan)
        assert len(warnings) >= 3  # description + steps + assignee

    def test_missing_keys_graceful(self):
        """Plan dict with missing keys should not crash."""
        plan = {}
        warnings = _validate_plan_for_approval(plan)
        assert len(warnings) >= 3  # description + steps + assignee


class TestPlanApproveWithWarnings:
    """Test that approve endpoint includes validation warnings."""

    def test_approve_incomplete_plan_returns_warnings(self, db_conn, sample_project):
        """Approve a plan with missing fields — should return warnings."""
        import db as db_module
        import api.plans as plans_module

        original_get = db_module.get_db
        # Also patch in plans module (it imports get_db at module level)
        plans_module.get_db = lambda: db_conn

        # Create a minimal plan
        plan_id = gen_id()
        db_conn.execute(
            "INSERT INTO plans (id, project_id, description, steps, status, assignee) VALUES (?, ?, ?, ?, ?, ?)",
            (plan_id, sample_project["id"], "", "[]", "proposed", ""),
        )
        db_conn.commit()

        try:
            from api.plans import approve_plan
            status, resp = approve_plan(
                {"id": plan_id}, {}, None, {"x-actor": "test"}
            )
            assert status == 200
            assert "warnings" in resp
            assert len(resp["warnings"]) >= 3
        finally:
            db_module.get_db = original_get
            plans_module.get_db = original_get

    def test_approve_complete_plan_no_warnings(self, db_conn, sample_project):
        """Approve a complete plan — should NOT return warnings."""
        import db as db_module
        import api.plans as plans_module

        original_get = db_module.get_db
        plans_module.get_db = lambda: db_conn

        plan_id = gen_id()
        steps = json.dumps([{"title": "Step 1"}, {"title": "Step 2"}])
        db_conn.execute(
            "INSERT INTO plans (id, project_id, description, steps, status, assignee) VALUES (?, ?, ?, ?, ?, ?)",
            (plan_id, sample_project["id"], "Build feature X", steps, "proposed", "kai"),
        )
        db_conn.commit()

        try:
            from api.plans import approve_plan
            status, resp = approve_plan(
                {"id": plan_id}, {}, None, {"x-actor": "test"}
            )
            assert status == 200
            assert "warnings" not in resp or resp["warnings"] == []
        finally:
            db_module.get_db = original_get
            plans_module.get_db = original_get
