"""AgentBoard — Plan CRUD, approve/reject/execute workflow.

A Plan represents a proposed execution strategy for a mission (or standalone).
Plans have a lifecycle: proposed → approved → executing → completed (or rejected/cancelled).

Endpoints:
    GET    /api/projects/{slug}/plans           — list plans in project
    GET    /api/plans/{id}                      — single plan with details
    POST   /api/projects/{slug}/plans           — create plan (proposed)
    PATCH  /api/plans/{id}                      — update plan / change status
    DELETE /api/plans/{id}                      — delete plan
    POST   /api/plans/{id}/approve              — approve a proposed plan
    POST   /api/plans/{id}/reject               — reject a proposed plan
    POST   /api/plans/{id}/execute              — start executing an approved plan
    POST   /api/plans/{id}/complete             — mark execution as completed
"""

import json
from db import get_db, gen_id
from api import router
from api.validation import (
    validate_enum, validate_text, validate_steps,
    VALID_PLAN_STATUSES,
    MAX_DESCRIPTION_LENGTH, MAX_CONTEXT_LENGTH,
)
from webhook import on_plan_created, on_plan_status_changed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_body(body: bytes) -> dict:
    """Safely parse JSON body. Returns empty dict on empty body, None on invalid JSON."""
    if not body:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None


def _plan_row_to_dict(row) -> dict:
    """Convert a plan Row to a plain dict with JSON fields parsed."""
    d = dict(row)
    for field in ("steps", "metadata"):
        raw = d.get(field)
        if isinstance(raw, str):
            try:
                d[field] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                d[field] = [] if field == "steps" else {}
    return d


def _log_activity(conn, project_id: str | None, target_type: str,
                  target_id: str | None, action: str, actor: str,
                  detail: dict | None = None):
    """Insert a row into the activity log."""
    conn.execute(
        """INSERT INTO activity (id, project_id, target_type, target_id, action, actor, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (gen_id(), project_id, target_type, target_id, action, actor,
         json.dumps(detail or {})),
    )


# Status transition rules
VALID_TRANSITIONS = {
    "proposed":   {"approved", "rejected"},
    "approved":   {"executing"},
    "executing":  {"done"},
    "done":       set(),
    "rejected":   set(),
}


def _can_transition(from_status: str, to_status: str) -> bool:
    """Check if a status transition is valid."""
    allowed = VALID_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def _resolve_project_slug(conn, project_id: str) -> str | None:
    """Resolve a project ID to its slug."""
    row = conn.execute("SELECT slug FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row["slug"] if row else None


# ---------------------------------------------------------------------------
# GET /api/projects/{slug}/plans
# ---------------------------------------------------------------------------

@router.get("/api/projects/{slug}/plans")
def list_plans(params, query, body, headers):
    """List all plans for a project, with optional filters."""
    slug = params["slug"]
    conn = get_db()

    project = conn.execute("SELECT id, slug FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not project:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project_id = project["id"]
    conditions = ["p.project_id = ?"]
    sql_params = [project_id]

    # Filter by status
    status_filter = query.get("status", [None])[0] if query.get("status") else None
    if status_filter:
        validated = validate_enum(status_filter, VALID_PLAN_STATUSES)
        if not validated:
            conn.close()
            return 400, {"error": f"Invalid status filter: '{status_filter}'", "code": "VALIDATION_ERROR"}
        conditions.append("p.status = ?")
        sql_params.append(validated)

    # Filter by mission_id
    mission_filter = query.get("mission_id", [None])[0] if query.get("mission_id") else None
    if mission_filter:
        conditions.append("p.mission_id = ?")
        sql_params.append(mission_filter.strip()[:20])

    # Filter by assignee
    assignee_filter = query.get("assignee", [None])[0] if query.get("assignee") else None
    if assignee_filter:
        conditions.append("p.assignee = ?")
        sql_params.append(assignee_filter.strip()[:200])

    where_clause = " AND ".join(conditions)

    rows = conn.execute(
        f"""SELECT p.* FROM plans p
            WHERE {where_clause}
            ORDER BY p.created_at DESC""",
        sql_params,
    ).fetchall()

    plans = [_plan_row_to_dict(r) for r in rows]
    conn.close()
    return 200, {"plans": plans, "total": len(plans)}


# ---------------------------------------------------------------------------
# GET /api/plans/{id}
# ---------------------------------------------------------------------------

@router.get("/api/plans/{id}")
def get_plan(params, query, body, headers):
    """Get a single plan by ID."""
    plan_id = params["id"]
    conn = get_db()

    row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Plan '{plan_id}' not found", "code": "NOT_FOUND"}

    plan = _plan_row_to_dict(row)

    # Attach mission title if mission_id is set
    if plan.get("mission_id"):
        mission = conn.execute(
            "SELECT title FROM tasks WHERE id = ?", (plan["mission_id"],)
        ).fetchone()
        if mission:
            plan["mission_title"] = mission["title"]

    conn.close()
    return 200, {"plan": plan}


# ---------------------------------------------------------------------------
# POST /api/projects/{slug}/plans
# ---------------------------------------------------------------------------

@router.post("/api/projects/{slug}/plans")
def create_plan(params, query, body, headers):
    """Create a new plan (status=proposed)."""
    slug = params["slug"]
    data = _parse_body(body)
    if data is None:
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    actor = headers.get("x-actor", "owner")

    conn = get_db()

    # Resolve project
    project = conn.execute("SELECT id, slug FROM projects WHERE slug = ?", (slug,)).fetchone()
    if not project:
        conn.close()
        return 404, {"error": f"Project '{slug}' not found", "code": "NOT_FOUND"}

    project_id = project["id"]

    # Validate required: description
    description = validate_text(data.get("description"), MAX_DESCRIPTION_LENGTH, "description")
    if not description:
        conn.close()
        return 400, {"error": "Plan description is required", "code": "VALIDATION_ERROR"}

    # Validate optional fields
    context = validate_text(data.get("context"), MAX_CONTEXT_LENGTH, "context")
    steps, steps_err = validate_steps(data.get("steps"))
    if steps_err:
        conn.close()
        return 400, {"error": steps_err, "code": "VALIDATION_ERROR"}
    assignee = validate_text(data.get("assignee"), 200, "assignee")
    mission_id = validate_text(data.get("mission_id"), 20, "mission_id") or None
    metadata = data.get("metadata") or {}

    # Validate mission_id exists in this project if provided
    if mission_id:
        mission = conn.execute(
            "SELECT id FROM tasks WHERE id = ? AND project_id = ?",
            (mission_id, project_id),
        ).fetchone()
        if not mission:
            conn.close()
            return 400, {"error": f"Mission task '{mission_id}' not found in this project", "code": "VALIDATION_ERROR"}

    plan_id = gen_id()
    created_by = (data.get("created_by") or actor).strip()

    conn.execute(
        """INSERT INTO plans (id, project_id, description, context, steps, status,
                             assignee, metadata, mission_id, created_by)
           VALUES (?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?)""",
        (plan_id, project_id, description, context, json.dumps(steps),
         assignee, json.dumps(metadata), mission_id, created_by),
    )

    _log_activity(conn, project_id, "plan", plan_id, "created", actor,
                  {"description": description[:100], "steps_count": len(steps)})

    plan = _plan_row_to_dict(
        conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    )

    on_plan_created(plan, actor, slug)

    conn.commit()
    conn.close()
    return 201, {"plan": plan}


# ---------------------------------------------------------------------------
# PATCH /api/plans/{id}
# ---------------------------------------------------------------------------

@router.patch("/api/plans/{id}")
def update_plan(params, query, body, headers):
    """Update plan fields (description, context, steps, assignee, metadata)."""
    plan_id = params["id"]
    data = _parse_body(body)
    if data is None:
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    actor = headers.get("x-actor", "owner")

    conn = get_db()
    row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Plan '{plan_id}' not found", "code": "NOT_FOUND"}

    plan = _plan_row_to_dict(row)
    updates = {}
    detail_changes = {}

    # Description
    if "description" in data:
        description = validate_text(data["description"], MAX_DESCRIPTION_LENGTH, "description")
        if not description:
            conn.close()
            return 400, {"error": "Plan description is required", "code": "VALIDATION_ERROR"}
        updates["description"] = description
        detail_changes["description"] = description[:100]

    # Context
    if "context" in data:
        updates["context"] = validate_text(data["context"], MAX_CONTEXT_LENGTH, "context")

    # Steps
    if "steps" in data:
        steps, steps_err = validate_steps(data["steps"])
        if steps_err:
            conn.close()
            return 400, {"error": steps_err, "code": "VALIDATION_ERROR"}
        updates["steps"] = json.dumps(steps)
        detail_changes["steps_count"] = len(steps)

    # Assignee
    if "assignee" in data:
        new_assignee = validate_text(data["assignee"], 200, "assignee")
        old_assignee = plan.get("assignee", "")
        if new_assignee != old_assignee:
            updates["assignee"] = new_assignee
            detail_changes["assignee"] = new_assignee or "(unassigned)"

    # Metadata
    if "metadata" in data and isinstance(data["metadata"], dict):
        updates["metadata"] = json.dumps(data["metadata"])

    # Mission ID
    if "mission_id" in data:
        new_mission = validate_text(data["mission_id"], 20, "mission_id") or None
        if new_mission != plan.get("mission_id"):
            if new_mission:
                mission = conn.execute(
                    "SELECT id FROM tasks WHERE id = ? AND project_id = ?",
                    (new_mission, plan["project_id"]),
                ).fetchone()
                if not mission:
                    conn.close()
                    return 400, {"error": f"Mission task '{new_mission}' not found in this project", "code": "VALIDATION_ERROR"}
            updates["mission_id"] = new_mission
            detail_changes["mission_id"] = new_mission

    if not updates:
        conn.close()
        return 200, {"plan": plan, "message": "No changes to apply"}

    # Apply updates
    set_parts = [f"{k} = ?" for k in updates]
    set_values = list(updates.values())
    set_parts.append("updated_at = datetime('now')")
    conn.execute(
        f"UPDATE plans SET {', '.join(set_parts)} WHERE id = ?",
        set_values + [plan_id],
    )

    _log_activity(conn, plan["project_id"], "plan", plan_id, "updated", actor, detail_changes)

    updated = _plan_row_to_dict(
        conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    )

    conn.commit()
    conn.close()
    return 200, {"plan": updated}


# ---------------------------------------------------------------------------
# DELETE /api/plans/{id}
# ---------------------------------------------------------------------------

@router.delete("/api/plans/{id}")
def delete_plan(params, query, body, headers):
    """Delete a plan (only proposed or rejected plans can be deleted)."""
    plan_id = params["id"]
    actor = headers.get("x-actor", "owner")

    conn = get_db()
    row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Plan '{plan_id}' not found", "code": "NOT_FOUND"}

    plan = _plan_row_to_dict(row)

    # Only proposed/rejected plans can be deleted
    if plan["status"] not in ("proposed", "rejected"):
        conn.close()
        return 400, {"error": f"Cannot delete plan in '{plan['status']}' status. Only proposed or rejected plans can be deleted.", "code": "VALIDATION_ERROR"}

    conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))

    _log_activity(conn, plan["project_id"], "plan", plan_id, "deleted", actor,
                  {"description": plan.get("description", "")[:100]})

    conn.commit()
    conn.close()
    return 200, {"message": "Plan deleted", "plan_id": plan_id}


# ---------------------------------------------------------------------------
# Status transition endpoints (POST)
# ---------------------------------------------------------------------------

def _status_transition(plan_id: str, target_status: str, actor: str, body: bytes | None = None):
    """Generic status transition handler.

    Returns (status_code, response_dict).
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Plan '{plan_id}' not found", "code": "NOT_FOUND"}

    plan = _plan_row_to_dict(row)
    old_status = plan["status"]

    if not _can_transition(old_status, target_status):
        conn.close()
        return 400, {"error": f"Cannot transition from '{old_status}' to '{target_status}'. Allowed: {sorted(VALID_TRANSITIONS.get(old_status, set()))}", "code": "TRANSITION_ERROR"}

    # Optionally allow updating steps/context on approve/execute
    if body and target_status in ("approved", "executing"):
        data = _parse_body(body) or {}
        if "steps" in data:
            steps, steps_err = validate_steps(data["steps"])
            if steps_err:
                conn.close()
                return 400, {"error": steps_err, "code": "VALIDATION_ERROR"}
            conn.execute("UPDATE plans SET steps = ? WHERE id = ?", (json.dumps(steps), plan_id))

    conn.execute(
        "UPDATE plans SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (target_status, plan_id),
    )

    _log_activity(conn, plan["project_id"], "plan", plan_id, f"status_{target_status}", actor,
                  {"old_status": old_status, "new_status": target_status})

    updated = _plan_row_to_dict(
        conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
    )

    project_slug = _resolve_project_slug(conn, plan["project_id"])
    on_plan_status_changed(updated, old_status, target_status, project_slug or "")

    conn.commit()
    conn.close()
    return 200, {"plan": updated}


@router.post("/api/plans/{id}/approve")
def approve_plan(params, query, body, headers):
    """Approve a proposed plan. Optionally update steps in the same call."""
    return _status_transition(params["id"], "approved", headers.get("x-actor", "owner"), body)


@router.post("/api/plans/{id}/reject")
def reject_plan(params, query, body, headers):
    """Reject a proposed plan."""
    return _status_transition(params["id"], "rejected", headers.get("x-actor", "owner"))


@router.post("/api/plans/{id}/execute")
def execute_plan(params, query, body, headers):
    """Start executing an approved plan."""
    return _status_transition(params["id"], "executing", headers.get("x-actor", "owner"), body)


@router.post("/api/plans/{id}/complete")
def complete_plan(params, query, body, headers):
    """Mark an executing plan as done."""
    return _status_transition(params["id"], "done", headers.get("x-actor", "owner"))
