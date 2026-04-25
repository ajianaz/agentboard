"""AgentBoard — FTS5 full-text search endpoints.

Endpoints:
    GET /api/search?q={query}                — search tasks + pages
    GET /api/search?q={query}&project={slug} — search within project
    GET /api/search?q={query}&type=task      — search only tasks
"""

from db import get_db
from api import router


@router.get("/api/search")
def search(params, query, body, headers):
    """Full-text search across tasks and pages using FTS5.

    Query params:
        q       — search query (required)
        project — filter by project slug (optional)
        type    — "task" or "page" to restrict search scope (optional)
        limit   — max results per type (default 20, max 100)
    """
    # Validate required query parameter
    q_list = query.get("q", [])
    q = q_list[0].strip() if q_list else ""
    if not q:
        return 400, {"error": "Query parameter 'q' is required", "code": "VALIDATION_ERROR"}

    # Parse optional filters
    project_slug = query.get("project", [None])[0]
    search_type = query.get("type", [None])[0]
    if search_type and search_type not in ("task", "page"):
        search_type = None

    try:
        limit = min(int(query.get("limit", ["20"])[0]), 100)
    except (ValueError, IndexError):
        limit = 20
    if limit < 1:
        limit = 20

    conn = get_db()

    # Build project filter clause (shared between task and page queries)
    project_join = ""
    project_where = ""
    if project_slug:
        project_join = "JOIN projects proj ON t.project_id = proj.id"
        project_where = "AND proj.slug = ?"

    results = []

    # --- Search tasks ---
    if search_type is None or search_type == "task":
        task_sql = f"""
            SELECT
                tasks.id,
                tasks_fts.title,
                snippet(tasks_fts, 0, '<mark>', '</mark>', '...', 32) as snippet,
                tasks_fts.rank,
                proj.slug as project_slug,
                proj.name as project_name
            FROM tasks_fts
            JOIN tasks ON tasks.rowid = tasks_fts.rowid
            JOIN projects proj ON tasks.project_id = proj.id
            WHERE tasks_fts MATCH ?
            {project_where if project_slug else ""}
            ORDER BY rank
            LIMIT ?
        """
        task_params = [q]
        if project_slug:
            task_params.append(project_slug)
        task_params.append(limit)

        for row in conn.execute(task_sql, task_params).fetchall():
            results.append({
                "type": "task",
                "id": row["id"],
                "title": row["title"],
                "snippet": row["snippet"] or "",
                "project_slug": row["project_slug"],
                "project_name": row["project_name"],
                "rank": round(row["rank"], 4),
            })

    # --- Search pages ---
    if search_type is None or search_type == "page":
        page_sql = f"""
            SELECT
                pages.id,
                pages_fts.title,
                snippet(pages_fts, 1, '<mark>', '</mark>', '...', 32) as snippet,
                pages_fts.rank,
                proj.slug as project_slug,
                proj.name as project_name
            FROM pages_fts
            JOIN pages ON pages.rowid = pages_fts.rowid
            JOIN projects proj ON pages.project_id = proj.id
            WHERE pages_fts MATCH ?
            {project_where if project_slug else ""}
            ORDER BY rank
            LIMIT ?
        """
        page_params = [q]
        if project_slug:
            page_params.append(project_slug)
        page_params.append(limit)

        for row in conn.execute(page_sql, page_params).fetchall():
            results.append({
                "type": "page",
                "id": row["id"],
                "title": row["title"],
                "snippet": row["snippet"] or "",
                "project_slug": row["project_slug"],
                "project_name": row["project_name"],
                "rank": round(row["rank"], 4),
            })

    # Sort all results by rank (best first), then by type for stable ordering
    results.sort(key=lambda r: (-r["rank"], r["type"], r["id"]))

    conn.close()

    return 200, {
        "results": results,
        "query": q,
        "total": len(results),
    }
