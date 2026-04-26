"""api/auth_keys — API key CRUD and rotation management endpoints.

Requires authentication (owner only). All routes return 401 without valid key.

Routes:
    GET    /api/auth/keys          — list all keys (hashed, never raw)
    POST   /api/auth/keys          — create new key (returns raw key ONCE)
    PATCH  /api/auth/keys/{id}     — update key label or deactivate (with grace period)
    DELETE /api/auth/keys/{id}     — permanently delete a key
"""

import json
from datetime import datetime, timezone, timedelta

from api import router
from db import get_db, gen_id
from auth import generate_api_key, hash_key, validate_key_against_db


@router.get("/api/auth/keys")
def list_keys(params, query, body, headers):
    """List all API keys. Raw keys are never returned."""
    conn = get_db()
    rows = conn.execute(
        """SELECT id, label, is_active, created_at, last_used_at, grace_until
           FROM api_keys ORDER BY created_at DESC"""
    ).fetchall()
    conn.close()
    keys = [dict(r) for r in rows]
    return 200, {"keys": keys}


@router.post("/api/auth/keys")
def create_key(params, query, body, headers):
    """Create a new API key. Returns the raw key exactly once."""
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, TypeError):
        return 400, {"error": "Invalid JSON", "code": "BAD_REQUEST"}

    label = data.get("label", "").strip() or "generated"
    raw_key = generate_api_key()
    key_hash = hash_key(raw_key)
    kid = gen_id()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO api_keys (id, key_hash, label, is_active, created_at)
               VALUES (?, ?, ?, 1, ?)""",
            (kid, key_hash, label, now),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        import sqlite3
        if isinstance(e, sqlite3.IntegrityError):
            return 409, {"error": "Key hash collision — retry", "code": "CONFLICT"}
        raise  # let the generic 500 handler catch it

    conn.close()
    return 201, {
        "id": kid,
        "label": label,
        "key": raw_key,  # shown ONLY on creation
        "created_at": now,
        "warning": "Save this key now — it cannot be retrieved again.",
    }


@router.patch("/api/auth/keys/{id}")
def update_key(params, query, body, headers):
    """Update a key's label or deactivate it with optional grace period."""
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, TypeError):
        return 400, {"error": "Invalid JSON", "code": "BAD_REQUEST"}

    kid = params.get("id")
    conn = get_db()
    row = conn.execute("SELECT id FROM api_keys WHERE id = ?", (kid,)).fetchone()

    if not row:
        conn.close()
        return 404, {"error": "Key not found", "code": "NOT_FOUND"}

    updates = []
    values = []

    if "label" in data:
        updates.append("label = ?")
        values.append(data["label"].strip())

    # Deactivate and activate are mutually exclusive — activate wins
    if data.get("is_active") is True:
        updates.append("is_active = 1")
        updates.append("grace_until = NULL")
    elif data.get("is_active") is False or data.get("deactivate") is True:
        # Deactivate with optional grace period
        grace_minutes = data.get("grace_minutes", 5)
        if grace_minutes and grace_minutes > 0:
            grace_until = (
                datetime.now(timezone.utc) + timedelta(minutes=grace_minutes)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            updates.append("grace_until = ?")
            values.append(grace_until)
        else:
            updates.append("grace_until = NULL")
        updates.append("is_active = 0")

    if not updates:
        conn.close()
        return 400, {"error": "No fields to update", "code": "BAD_REQUEST"}

    values.append(kid)
    conn.execute(f"UPDATE api_keys SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()

    # Return updated key
    row = conn.execute(
        """SELECT id, label, is_active, created_at, last_used_at, grace_until
           FROM api_keys WHERE id = ?""",
        (kid,),
    ).fetchone()
    conn.close()
    return 200, {"key": dict(row)}


@router.delete("/api/auth/keys/{id}")
def delete_key(params, query, body, headers):
    """Permanently delete an API key. Cannot be undone."""
    kid = params.get("id")
    conn = get_db()

    # Prevent deleting the last active key
    active_count = conn.execute(
        "SELECT COUNT(*) as c FROM api_keys WHERE is_active = 1 AND id != ?",
        (kid,),
    ).fetchone()

    row = conn.execute("SELECT id, is_active FROM api_keys WHERE id = ?", (kid,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": "Key not found", "code": "NOT_FOUND"}

    if row["is_active"] and active_count["c"] == 0:
        conn.close()
        return 409, {
            "error": "Cannot delete the last active key",
            "code": "LAST_KEY",
        }

    conn.execute("DELETE FROM api_keys WHERE id = ?", (kid,))
    conn.commit()
    conn.close()
    return 200, {"deleted": kid}
