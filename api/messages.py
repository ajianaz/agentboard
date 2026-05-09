"""AgentBoard — Messages API for lightweight inter-agent handoffs.

Unlike discussions (multi-round, structured, with verdicts), messages are
simple point-to-point notifications: "I finished my part, you can start."

Endpoints:
    POST   /api/messages                        — send a message
    GET    /api/messages?agent={name}           — inbox for agent (unread first)
    GET    /api/messages?agent={name}&all=1     — all messages (incl. read)
    PATCH  /api/messages/{id}/read              — mark as read
    DELETE /api/messages/{id}                   — delete message
"""

import json
from db import get_db, gen_id
from api import require_permission, router
from api.validation import validate_text


# ---------------------------------------------------------------------------
# POST /api/messages — send message
# ---------------------------------------------------------------------------

@router.post("/api/messages")
@require_permission("write")
def send_message(params, query, body, headers):
    """Send a message to an agent (or broadcast to all with to_agent='')."""
    data = _parse_msg_body(body)
    if data is None:
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}

    from_agent = headers.get("x-actor", "").strip() or validate_text(data.get("from_agent"), 100, "from_agent")
    if not from_agent:
        return 400, {"error": "from_agent is required (via header x-actor or body)", "code": "VALIDATION_ERROR"}

    to_agent = validate_text(data.get("to_agent"), 100, "to_agent") or ""
    subject = validate_text(data.get("subject"), 200, "subject") or ""
    content = validate_text(data.get("content"), 2000, "content")
    if not content:
        return 400, {"error": "content is required", "code": "VALIDATION_ERROR"}
    task_id = validate_text(data.get("task_id"), 20, "task_id") or None

    # Validate task_id if provided
    conn = get_db()
    if task_id:
        task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            conn.close()
            return 400, {"error": f"Task '{task_id}' not found", "code": "NOT_FOUND"}

    msg_id = gen_id()
    conn.execute(
        """INSERT INTO messages (id, from_agent, to_agent, task_id, subject, content)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (msg_id, from_agent, to_agent, task_id, subject, content),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
    msg = dict(row) if row else None
    conn.close()

    if msg:
        return 201, {"message": msg}
    return 500, {"error": "Failed to create message", "code": "INTERNAL_ERROR"}


# ---------------------------------------------------------------------------
# GET /api/messages — inbox
# ---------------------------------------------------------------------------

@router.get("/api/messages")
def list_messages(params, query, body, headers):
    """List messages for an agent. Defaults to unread-only; ?all=1 for all.
    Without agent param or x-actor header, shows all messages (public/admin view)."""
    agent = query.get("agent", [""])[0] if query.get("agent") else headers.get("x-actor", "")

    show_all = query.get("all", [""])[0] == "1"

    conn = get_db()

    if agent:
        if show_all:
            rows = conn.execute(
                """SELECT m.* FROM messages m
                   WHERE m.to_agent = '' OR m.to_agent = ? OR m.from_agent = ?
                   ORDER BY m.is_read ASC, m.created_at DESC
                   LIMIT 100""",
                (agent, agent),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT m.* FROM messages m
                   WHERE (m.to_agent = '' OR m.to_agent = ?)
                   AND m.is_read = 0
                   ORDER BY m.created_at DESC
                   LIMIT 50""",
                (agent,),
            ).fetchall()

        # Count unread
        unread_row = conn.execute(
            """SELECT COUNT(*) as cnt FROM messages
               WHERE (to_agent = '' OR to_agent = ?) AND is_read = 0""",
            (agent,),
        ).fetchone()
        unread_count = unread_row["cnt"] if unread_row else 0
    else:
        # Public view — show all messages
        rows = conn.execute(
            """SELECT m.* FROM messages m
               ORDER BY m.created_at DESC
               LIMIT 100"""
        ).fetchall()
        unread_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE is_read = 0"
        ).fetchone()
        unread_count = unread_row["cnt"] if unread_row else 0

    messages = [dict(r) for r in rows]

    conn.close()
    return 200, {"messages": messages, "unread_count": unread_count}


# ---------------------------------------------------------------------------
# PATCH /api/messages/{id}/read — mark as read
# ---------------------------------------------------------------------------

@router.patch("/api/messages/{id}/read")
@require_permission("write")
def mark_read(params, query, body, headers):
    """Mark a message as read."""
    msg_id = params["id"]
    conn = get_db()

    row = conn.execute("SELECT id FROM messages WHERE id = ?", (msg_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Message '{msg_id}' not found", "code": "NOT_FOUND"}

    conn.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()

    return 200, {"read": True, "id": msg_id}


# ---------------------------------------------------------------------------
# PATCH /api/messages/read-all — mark all as read for agent
# ---------------------------------------------------------------------------

@router.patch("/api/messages/read-all")
@require_permission("write")
def mark_all_read(params, query, body, headers):
    """Mark all unread messages for an agent as read."""
    agent = headers.get("x-actor", "")
    if not agent:
        return 400, {"error": "x-actor header required", "code": "VALIDATION_ERROR"}

    conn = get_db()
    cursor = conn.execute(
        "UPDATE messages SET is_read = 1 WHERE (to_agent = '' OR to_agent = ?) AND is_read = 0",
        (agent,),
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()

    return 200, {"read_count": count}


# ---------------------------------------------------------------------------
# DELETE /api/messages/{id}
# ---------------------------------------------------------------------------

@router.delete("/api/messages/{id}")
@require_permission("write")
def delete_message(params, query, body, headers):
    """Delete a message."""
    msg_id = params["id"]
    conn = get_db()

    row = conn.execute("SELECT id FROM messages WHERE id = ?", (msg_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": f"Message '{msg_id}' not found", "code": "NOT_FOUND"}

    conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()

    return 200, {"deleted": True, "id": msg_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_msg_body(body: bytes) -> dict:
    """Safely parse JSON body."""
    if not body:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
