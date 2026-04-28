"""AgentBoard — Agent management and workload endpoints.

Endpoints:
    GET    /api/agents              — list all agents
    POST   /api/agents              — register agent
    GET    /api/agents/{id}         — get single agent
    PATCH  /api/agents/{id}         — update agent
    GET    /api/agents/{id}/workload — agent task stats across all projects
"""

import json
from db import get_db, gen_id
from api import router
from api.validation import validate_text, MAX_NAME_LENGTH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_agent_fields(data: dict) -> dict:
    """Enforce lowercase on agent id and name — prevents casing mismatches
    between agents table, task assignees, and KPI agent_id columns."""
    for key in ("id", "name"):
        if key in data and isinstance(data[key], str):
            data[key] = data[key].strip().lower()
    return data


def _parse_body(body: bytes) -> dict:
    """Safely parse JSON body. Returns empty dict on empty body, None on invalid JSON."""
    if not body:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None


def _agent_row_to_dict(row) -> dict:
    """Convert an agent Row to a plain dict with JSON fields parsed."""
    d = dict(row)
    for field in ("metadata",):
        raw = d.get(field)
        if isinstance(raw, str):
            try:
                d[field] = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                d[field] = {}
    return d


# ---------------------------------------------------------------------------
# GET /api/agents — list all agents
# ---------------------------------------------------------------------------

@router.get("/api/agents")
def list_agents(params, query, body, headers):
    conn = get_db()

    rows = conn.execute(
        "SELECT * FROM agents ORDER BY name ASC"
    ).fetchall()

    agents = [_agent_row_to_dict(r) for r in rows]
    conn.close()
    return 200, {"agents": agents}


# ---------------------------------------------------------------------------
# POST /api/agents — register agent
# ---------------------------------------------------------------------------

@router.post("/api/agents")
def create_agent(params, query, body, headers):
    data = _parse_body(body)
    if data is None:
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    actor = headers.get("x-actor", "owner")
    _normalize_agent_fields(data)

    agent_id = validate_text(data.get("id"), 100, "Agent ID")
    if not agent_id:
        return 400, {"error": "Agent id is required", "code": "VALIDATION_ERROR"}

    name = validate_text(data.get("name"), MAX_NAME_LENGTH, "Agent name")
    if not name:
        return 400, {"error": "Agent name is required", "code": "VALIDATION_ERROR"}

    role = validate_text(data.get("role"), 200, "Agent role")
    avatar = (data.get("avatar") or "🤖").strip()
    color = (data.get("color") or "#3b82f6").strip()
    metadata = data.get("metadata") or {}

    conn = get_db()

    # Check for existing agent with same id
    existing = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if existing:
        conn.close()
        return 409, {"error": f"Agent '{agent_id}' already exists", "code": "CONFLICT"}

    conn.execute(
        """INSERT INTO agents (id, name, role, avatar, color, metadata)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (agent_id, name, role, avatar, color, json.dumps(metadata)),
    )

    conn.commit()

    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    agent = _agent_row_to_dict(row)
    conn.close()

    return 201, {"agent": agent}


# ---------------------------------------------------------------------------
# GET /api/agents/{id} — get single agent
# ---------------------------------------------------------------------------

@router.get("/api/agents/{id}")
def get_agent(params, query, body, headers):
    agent_id = params["id"].lower()
    conn = get_db()

    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Agent '{agent_id}' not found", "code": "NOT_FOUND"}

    agent = _agent_row_to_dict(row)
    conn.close()
    return 200, {"agent": agent}


# ---------------------------------------------------------------------------
# PATCH /api/agents/{id} — update agent
# ---------------------------------------------------------------------------

@router.patch("/api/agents/{id}")
def update_agent(params, query, body, headers):
    agent_id = params["id"].lower()  # normalize path param too
    data = _parse_body(body)
    if data is None:
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    actor = headers.get("x-actor", "owner")
    _normalize_agent_fields(data)

    conn = get_db()

    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Agent '{agent_id}' not found", "code": "NOT_FOUND"}

    updates = {}

    # Name
    if "name" in data and data["name"] is not None:
        new_name = validate_text(str(data["name"]), MAX_NAME_LENGTH, "Agent name").lower()  # already normalized, but be explicit
        if not new_name:
            conn.close()
            return 400, {"error": "Agent name cannot be empty", "code": "VALIDATION_ERROR"}
        updates["name"] = new_name

    # Role
    if "role" in data and data["role"] is not None:
        updates["role"] = validate_text(data["role"], 200, "Agent role")

    # Avatar
    if "avatar" in data and data["avatar"] is not None:
        updates["avatar"] = str(data["avatar"]).strip()

    # Color
    if "color" in data and data["color"] is not None:
        updates["color"] = str(data["color"]).strip()

    # is_active
    if "is_active" in data and data["is_active"] is not None:
        try:
            updates["is_active"] = int(data["is_active"])
        except (ValueError, TypeError):
            pass

    # Metadata
    if "metadata" in data and data["metadata"] is not None:
        updates["metadata"] = json.dumps(data["metadata"])

    if not updates:
        conn.close()
        return 200, {"agent": _agent_row_to_dict(row)}

    # Build SET clause
    set_parts = []
    set_values = []
    for key, val in updates.items():
        set_parts.append(f"{key} = ?")
        set_values.append(val)
    set_values.append(agent_id)

    conn.execute(
        f"UPDATE agents SET {', '.join(set_parts)} WHERE id = ?",
        set_values,
    )

    conn.commit()
    updated = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    agent = _agent_row_to_dict(updated)
    conn.close()

    return 200, {"agent": agent}


# ---------------------------------------------------------------------------
# GET /api/agents/{id}/workload — task counts by status across all projects
# ---------------------------------------------------------------------------

@router.get("/api/agents/{id}/workload")
def get_agent_workload(params, query, body, headers):
    agent_id = params["id"].lower()
    conn = get_db()

    # Verify agent exists
    agent = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not agent:
        conn.close()
        return 404, {"error": f"Agent '{agent_id}' not found", "code": "NOT_FOUND"}

    # Task counts grouped by status
    status_rows = conn.execute(
        """SELECT status, COUNT(*) as count
           FROM tasks
           WHERE assignee = ?
           GROUP BY status""",
        (agent_id,),
    ).fetchall()
    by_status = {r["status"]: r["count"] for r in status_rows}
    total = sum(by_status.values())
    completed = by_status.get("done", 0)

    # Active project names (projects with at least one task assigned to this agent)
    project_rows = conn.execute(
        """SELECT DISTINCT p.id, p.name, p.slug
           FROM projects p
           JOIN tasks t ON t.project_id = p.id
           WHERE t.assignee = ? AND p.is_archived = 0
           ORDER BY p.name ASC""",
        (agent_id,),
    ).fetchall()
    active_projects = [{"id": r["id"], "name": r["name"], "slug": r["slug"]} for r in project_rows]

    conn.close()

    return 200, {
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "by_status": by_status,
        "total": total,
        "completed": completed,
        "active_projects": active_projects,
    }
