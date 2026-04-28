"""api/discussions.py - Discussion and review system endpoints.

Multi-participant discussion/review system for AgentBoard. Allows agents or team
members to review proposals/tasks with structured feedback across multiple rounds.

Endpoints:
    GET    /api/discussions              — list all discussions
    GET    /api/discussions/{id}         — get discussion with all feedback
    POST   /api/discussions              — create new discussion
    PATCH  /api/discussions/{id}         — update discussion (status, round)
    DELETE /api/discussions/{id}         — delete discussion
    POST   /api/discussions/{id}/feedback — add feedback for a round
    GET    /api/discussions/{id}/summary  — aggregated verdict summary
"""

import json
from db import get_db, gen_id
from activity_logger import log_activity_event, get_actor_from_headers
from api import router, is_authenticated
from api.validation import validate_title, validate_text, validate_enum, MAX_TITLE_LENGTH, MAX_COMMENT_LENGTH, VALID_DISCUSSION_STATUSES, VALID_VISIBILITIES, VALID_VERDICTS
from webhook import on_discussion_created, on_discussion_feedback, on_discussion_closed


def _discussion_row_to_dict(row) -> dict:
    """Convert a discussion Row to a plain dict, parsing JSON fields."""
    d = dict(row)
    # Parse participants JSON string -> list
    raw = d.get("participants")
    if isinstance(raw, str):
        try:
            d["participants"] = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            d["participants"] = []
    return d


def _feedback_row_to_dict(row) -> dict:
    """Convert a feedback Row to a plain dict."""
    return dict(row)


@router.get("/api/discussions")
def list_discussions(params, query, body, headers):
    """List discussions, optionally filtered.

    Query params:
        target_type — filter by target type (task, page, project)
        target_id   — filter by target ID
        status      — filter by status (open, closed, consensus)
        limit       — max rows (default 50, max 200)
        offset      — skip N rows (default 0)
    """
    try:
        limit = min(int(query.get("limit", ["50"])[0]), 200)
    except (ValueError, IndexError):
        limit = 50
    try:
        offset = max(int(query.get("offset", ["0"])[0]), 0)
    except (ValueError, IndexError):
        offset = 0

    target_type = query.get("target_type", [None])[0]
    target_id = query.get("target_id", [None])[0]
    status = query.get("status", [None])[0]

    conditions = []
    sql_params = []

    if target_type:
        conditions.append("d.target_type = ?")
        sql_params.append(target_type)
    if target_id:
        conditions.append("d.target_id = ?")
        sql_params.append(target_id)
    if status:
        conditions.append("d.status = ?")
        sql_params.append(status)

    # Visibility filter: hidden discussions only visible to their creator
    # Unauthenticated users only see public discussions
    actor = get_actor_from_headers(headers) if is_authenticated(headers) else None
    if actor:
        conditions.append("(d.visibility = 'public' OR d.created_by = ?)")
        sql_params.append(actor)
    else:
        conditions.append("d.visibility = 'public'")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    conn = get_db()
    rows = conn.execute(
        f"""SELECT d.*, 
                   (SELECT COUNT(*) FROM discussion_feedback df WHERE df.discussion_id = d.id) as feedback_count
            FROM discussions d
            {where}
            ORDER BY d.updated_at DESC
            LIMIT ? OFFSET ?""",
        (*sql_params, limit, offset),
    ).fetchall()

    count_row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM discussions d {where}",
        (*sql_params,),
    ).fetchone()

    discussions = [_discussion_row_to_dict(r) for r in rows]
    conn.close()

    return 200, {
        "discussions": discussions,
        "total": count_row["cnt"],
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/discussions/{id}")
def get_discussion(params, query, body, headers):
    """Get a single discussion with all feedback ordered by round."""
    discussion_id = params["id"]
    conn = get_db()

    row = conn.execute(
        "SELECT * FROM discussions WHERE id = ?", (discussion_id,)
    ).fetchone()

    if not row:
        conn.close()
        return 404, {"error": "Discussion not found", "code": "NOT_FOUND"}

    # Visibility check: hidden discussions only accessible by their creator
    if row["visibility"] != "public":
        actor = get_actor_from_headers(headers) if is_authenticated(headers) else None
        if not actor or actor != row["created_by"]:
            conn.close()
            return 404, {"error": "Discussion not found", "code": "NOT_FOUND"}

    # Get all feedback ordered by round, then participant
    feedback_rows = conn.execute(
        """SELECT * FROM discussion_feedback
           WHERE discussion_id = ?
           ORDER BY round ASC, participant ASC""",
        (discussion_id,),
    ).fetchall()

    discussion = _discussion_row_to_dict(row)
    discussion["feedback"] = [_feedback_row_to_dict(r) for r in feedback_rows]
    conn.close()

    return 200, discussion


@router.post("/api/discussions")
def create_discussion(params, query, body, headers):
    """Create a new discussion.

    Body:
        title        — discussion title (required)
        target_type  — optional (task, page, project)
        target_id    — optional
        max_rounds   — optional (default 5)
        created_by   — optional (auto-detected from X-Actor header)
    """
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    title, title_err = validate_title(data.get("title"), MAX_TITLE_LENGTH, "Discussion title")
    if title_err:
        return 400, {"error": title_err, "code": "VALIDATION_ERROR"}

    # Validate leader and participants when creating via coordinator
    # (raw API calls without these fields create zombie discussions)
    participants_raw = data.get("participants", [])
    leader = data.get("leader", "").strip()
    context = data.get("context", "").strip()

    conn = get_db()
    discussion_id = gen_id()
    actor = data.get("created_by") or get_actor_from_headers(headers)
    max_rounds = min(int(data.get("max_rounds", 5)), 20)

    # participants as JSON string
    participants_json = json.dumps(participants_raw) if isinstance(participants_raw, list) else str(participants_raw)

    conn.execute(
        """INSERT INTO discussions (id, title, target_type, target_id, status, current_round, max_rounds, created_by, created_at, updated_at, context, participants, leader)
           VALUES (?, ?, ?, ?, 'open', 1, ?, ?, datetime('now'), datetime('now'), ?, ?, ?)""",
        (discussion_id, title, data.get("target_type", ""), data.get("target_id", ""),
         max_rounds, actor,
         context, participants_json, leader),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
    conn.close()

    log_activity_event("discussion", discussion_id, "create", actor,
                       {"title": title, "target_type": data.get("target_type", "")})

    discussion_dict = _discussion_row_to_dict(row)
    on_discussion_created(discussion_dict, actor)

    return 201, discussion_dict


@router.patch("/api/discussions/{id}")
def update_discussion(params, query, body, headers):
    """Update a discussion.

    Body (any combination):
        title   — new title
        status  — open, closed, consensus
        current_round — advance to next round
    """
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    discussion_id = params["id"]
    actor = get_actor_from_headers(headers)

    conn = get_db()
    row = conn.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": "Discussion not found", "code": "NOT_FOUND"}

    updates = []
    update_params = []

    if "title" in data and data["title"] and data["title"].strip():
        title_val, title_err = validate_title(data["title"], MAX_TITLE_LENGTH, "Discussion title")
        if title_err:
            return 400, {"error": title_err, "code": "VALIDATION_ERROR"}
        updates.append("title = ?")
        update_params.append(title_val)
    if "status" in data:
        status_val = validate_enum(data["status"], VALID_DISCUSSION_STATUSES)
        if status_val is not None:
            updates.append("status = ?")
            update_params.append(status_val)
    if "current_round" in data:
        updates.append("current_round = ?")
        update_params.append(min(int(data["current_round"]), row["max_rounds"]))
    if "context" in data:
        updates.append("context = ?")
        update_params.append(validate_text(data["context"], MAX_DESCRIPTION_LENGTH, "Discussion context"))
    if "leader" in data:
        updates.append("leader = ?")
        update_params.append(validate_text(data["leader"], 200, "Discussion leader"))
    if "participants" in data:
        raw = data["participants"]
        participants_json = json.dumps(raw) if isinstance(raw, list) else str(raw)
        updates.append("participants = ?")
        update_params.append(participants_json)
    if "visibility" in data:
        vis = validate_enum(data["visibility"], VALID_VISIBILITIES)
        if vis is not None:
            updates.append("visibility = ?")
            update_params.append(vis)

    if updates:
        updates.append("updated_at = datetime('now')")
        conn.execute(
            f"UPDATE discussions SET {', '.join(updates)} WHERE id = ?",
            (*update_params, discussion_id),
        )
        conn.commit()

    row = conn.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
    conn.close()

    log_activity_event("discussion", discussion_id, "update", actor, data)

    discussion_dict = _discussion_row_to_dict(row)
    # Fire webhook if discussion was closed or reached consensus
    if "status" in data and data["status"] in ("closed", "consensus"):
        on_discussion_closed(discussion_dict, actor)

    return 200, discussion_dict


@router.delete("/api/discussions/{id}")
def delete_discussion(params, query, body, headers):
    """Delete a discussion and all its feedback."""
    discussion_id = params["id"]
    actor = get_actor_from_headers(headers)

    conn = get_db()
    row = conn.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": "Discussion not found", "code": "NOT_FOUND"}

    conn.execute("DELETE FROM discussion_feedback WHERE discussion_id = ?", (discussion_id,))
    conn.execute("DELETE FROM discussions WHERE id = ?", (discussion_id,))
    conn.commit()
    conn.close()

    log_activity_event("discussion", discussion_id, "delete", actor)
    return 200, {"deleted": True}


@router.post("/api/discussions/{id}/feedback")
def add_feedback(params, query, body, headers):
    """Add feedback for a discussion round.

    Body:
        participant — participant name/ID (required)
        role        — optional role description
        verdict     — approve, conditional, reject, or empty
        content     — feedback text (required)
        round       — optional round number (defaults to current_round)
    """
    try:
        data = json.loads(body) if body else {}
    except (json.JSONDecodeError, ValueError):
        return 400, {"error": "Invalid JSON in request body", "code": "BAD_REQUEST"}
    discussion_id = params["id"]
    participant = validate_text(data.get("participant"), 200, "Participant")
    content = validate_text(data.get("content"), MAX_COMMENT_LENGTH, "Feedback content")

    if not participant:
        return 400, {"error": "Participant is required", "code": "VALIDATION_ERROR"}
    if not content:
        return 400, {"error": "Content is required", "code": "VALIDATION_ERROR"}

    verdict = validate_enum(data.get("verdict"), VALID_VERDICTS, default="")
    if verdict is None:
        return 400, {"error": "Invalid verdict. Use: approve, conditional, reject", "code": "VALIDATION_ERROR"}

    conn = get_db()
    row = conn.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": "Discussion not found", "code": "NOT_FOUND"}

    # Visibility check: hidden discussions only accessible by their creator
    if row["visibility"] != "public":
        actor = get_actor_from_headers(headers) if is_authenticated(headers) else None
        if not actor or actor != row["created_by"]:
            conn.close()
            return 404, {"error": "Discussion not found", "code": "NOT_FOUND"}

    # Reject feedback on closed discussions (AB-RACE-001)
    if row["status"] != "open":
        conn.close()
        return 400, {"error": "Discussion is not open for feedback", "code": "DISCUSSION_CLOSED"}

    # Use specified round or default to current round
    round_num = int(data.get("round", row["current_round"]))
    round_num = min(round_num, row["max_rounds"])

    # Atomic upsert — eliminates race condition (AB-RACE-001)
    feedback_id = gen_id()
    conn.execute('''
        INSERT INTO discussion_feedback (id, discussion_id, round, participant, role, verdict, content, word_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(discussion_id, round, participant) DO UPDATE SET
            role = excluded.role,
            verdict = excluded.verdict,
            content = excluded.content,
            word_count = excluded.word_count
    ''', (
        feedback_id, discussion_id, round_num, participant,
        data.get("role", ""), verdict, content, len(content.split()),
    ))

    # Update discussion's updated_at
    conn.execute(
        "UPDATE discussions SET updated_at = datetime('now') WHERE id = ?",
        (discussion_id,),
    )
    conn.commit()

    # Fetch updated feedback
    fb_row = conn.execute(
        """SELECT * FROM discussion_feedback
           WHERE discussion_id = ? AND round = ? AND participant = ?""",
        (discussion_id, round_num, participant),
    ).fetchone()
    conn.close()

    feedback_dict = _feedback_row_to_dict(fb_row)
    discussion_dict = _discussion_row_to_dict(row)
    on_discussion_feedback(discussion_dict, feedback_dict, participant)

    return 201, feedback_dict


@router.get("/api/discussions/{id}/summary")
def get_discussion_summary(params, query, body, headers):
    """Get aggregated verdict summary for a discussion.

    Returns per-round verdict counts and final consensus status.
    """
    discussion_id = params["id"]
    conn = get_db()

    row = conn.execute("SELECT * FROM discussions WHERE id = ?", (discussion_id,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": "Discussion not found", "code": "NOT_FOUND"}

    # Visibility check: hidden discussions only accessible by their creator
    if row["visibility"] != "public":
        actor = get_actor_from_headers(headers) if is_authenticated(headers) else None
        if not actor or actor != row["created_by"]:
            conn.close()
            return 404, {"error": "Discussion not found", "code": "NOT_FOUND"}

    # Get all feedback grouped by round
    feedback_rows = conn.execute(
        """SELECT round, participant, role, verdict, word_count
           FROM discussion_feedback
           WHERE discussion_id = ?
           ORDER BY round ASC, participant ASC""",
        (discussion_id,),
    ).fetchall()

    # Build per-round summary
    rounds = {}
    for fb in feedback_rows:
        r = fb["round"]
        if r not in rounds:
            rounds[r] = {"participants": [], "verdicts": {"approve": 0, "conditional": 0, "reject": 0, "": 0}}
        rounds[r]["participants"].append({
            "participant": fb["participant"],
            "role": fb["role"],
            "verdict": fb["verdict"],
            "word_count": fb["word_count"],
        })
        v = fb["verdict"] if fb["verdict"] in rounds[r]["verdicts"] else ""
        rounds[r]["verdicts"][v] += 1

    # Determine consensus
    all_verdicts = [fb["verdict"] for fb in feedback_rows if fb["verdict"]]
    if all_verdicts:
        approve_count = all_verdicts.count("approve")
        reject_count = all_verdicts.count("reject")
        total = len(all_verdicts)

        if reject_count == 0 and approve_count == total:
            consensus = "approved"
        elif reject_count > total / 2:
            consensus = "rejected"
        elif approve_count > total / 2:
            consensus = "approved_with_conditions"
        else:
            consensus = "in_progress"
    else:
        consensus = "no_feedback"

    conn.close()

    return 200, {
        "discussion_id": discussion_id,
        "title": row["title"],
        "status": row["status"],
        "current_round": row["current_round"],
        "max_rounds": row["max_rounds"],
        "rounds": rounds,
        "consensus": consensus,
        "total_feedback": len(feedback_rows),
    }
