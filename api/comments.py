"""AgentBoard — Comment CRUD for tasks and pages.

Endpoints:
    GET  /api/tasks/{id}/comments  — list comments for task (ASC by created_at)
    POST /api/tasks/{id}/comments  — add comment to task
    GET  /api/pages/{id}/comments  — list comments for page
    POST /api/pages/{id}/comments  — add comment to page
"""

import json
from db import get_db, gen_id
from api import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_body(body: bytes) -> dict:
    """Safely parse JSON body, returning empty dict on empty/invalid input."""
    if not body:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return {}


def _comment_row_to_dict(row) -> dict:
    """Convert a comment Row to a plain dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# GET /api/tasks/{id}/comments — list comments for task
# ---------------------------------------------------------------------------

@router.get("/api/tasks/{id}/comments")
def list_task_comments(params, query, body, headers):
    task_id = params["id"]
    conn = get_db()

    # Verify task exists
    task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return 404, {"error": f"Task '{task_id}' not found", "code": "NOT_FOUND"}

    rows = conn.execute(
        """SELECT * FROM comments
           WHERE target_type = 'task' AND target_id = ?
           ORDER BY created_at ASC""",
        (task_id,),
    ).fetchall()

    comments = [_comment_row_to_dict(r) for r in rows]
    conn.close()
    return 200, {"comments": comments}


# ---------------------------------------------------------------------------
# POST /api/tasks/{id}/comments — add comment to task
# ---------------------------------------------------------------------------

@router.post("/api/tasks/{id}/comments")
def create_task_comment(params, query, body, headers):
    task_id = params["id"]
    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    content = (data.get("content") or "").strip()
    if not content:
        return 400, {"error": "Comment content is required", "code": "VALIDATION_ERROR"}

    conn = get_db()

    # Verify task exists
    task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return 404, {"error": f"Task '{task_id}' not found", "code": "NOT_FOUND"}

    comment_id = gen_id()
    conn.execute(
        """INSERT INTO comments (id, target_type, target_id, author, content)
           VALUES (?, 'task', ?, ?, ?)""",
        (comment_id, task_id, actor, content),
    )

    conn.commit()

    row = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    comment = _comment_row_to_dict(row)
    conn.close()

    return 201, {"comment": comment}


# ---------------------------------------------------------------------------
# GET /api/pages/{id}/comments — list comments for page
# ---------------------------------------------------------------------------

@router.get("/api/pages/{id}/comments")
def list_page_comments(params, query, body, headers):
    page_id = params["id"]
    conn = get_db()

    # Verify page exists
    page = conn.execute("SELECT id FROM pages WHERE id = ?", (page_id,)).fetchone()
    if not page:
        conn.close()
        return 404, {"error": f"Page '{page_id}' not found", "code": "NOT_FOUND"}

    rows = conn.execute(
        """SELECT * FROM comments
           WHERE target_type = 'page' AND target_id = ?
           ORDER BY created_at ASC""",
        (page_id,),
    ).fetchall()

    comments = [_comment_row_to_dict(r) for r in rows]
    conn.close()
    return 200, {"comments": comments}


# ---------------------------------------------------------------------------
# POST /api/pages/{id}/comments — add comment to page
# ---------------------------------------------------------------------------

@router.post("/api/pages/{id}/comments")
def create_page_comment(params, query, body, headers):
    page_id = params["id"]
    data = _parse_body(body)
    actor = headers.get("x-actor", "owner")

    content = (data.get("content") or "").strip()
    if not content:
        return 400, {"error": "Comment content is required", "code": "VALIDATION_ERROR"}

    conn = get_db()

    # Verify page exists
    page = conn.execute("SELECT id FROM pages WHERE id = ?", (page_id,)).fetchone()
    if not page:
        conn.close()
        return 404, {"error": f"Page '{page_id}' not found", "code": "NOT_FOUND"}

    comment_id = gen_id()
    conn.execute(
        """INSERT INTO comments (id, target_type, target_id, author, content)
           VALUES (?, 'page', ?, ?, ?)""",
        (comment_id, page_id, actor, content),
    )

    conn.commit()

    row = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    comment = _comment_row_to_dict(row)
    conn.close()

    return 201, {"comment": comment}
