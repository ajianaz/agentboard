# AgentBoard Pitfalls & Troubleshooting

Common gotchas, edge cases, and how to handle them.

---

## Response Wrapping

**Problem:** POST responses wrap data in a resource key.

```python
# WRONG — trying to access slug directly
slug = response["slug"]  # KeyError!

# CORRECT — access via wrapper key
slug = response["project"]["slug"]
task_id = response["task"]["id"]
page_id = response["page"]["id"]
```

**Affected endpoints:** All POST endpoints return `{"project": {...}}`, `{"task": {...}}`, `{"page": {...}}`, etc.

**Exception:** `GET` endpoints return unwrapped lists: `{"projects": [...]}`, `{"tasks": [...]}`.

---

## Auth Header Format

**Problem:** Using wrong auth header name or format.

```python
# WRONG
headers = {"X-API-Key": key}           # Not supported
headers = {"Authorization": key}       # Missing "Bearer " prefix
headers = {"Authorization": f"Token {key}"}  # Wrong scheme

# CORRECT
headers = {"Authorization": f"Bearer {key}"}
```

**Error:** `401 {"error": "Unauthorized", "code": "UNAUTHORIZED"}`

---

## Slug vs ID

**Problem:** Mixing up slug and ID for different resources.

| Resource | Identifier | Example |
|----------|-----------|---------|
| Projects | `slug` (string) | `website-redesign` |
| Tasks | `id` (hex) | `4f59be5bdef1d782` |
| Pages | `id` (hex) | `cb6fb862de4bec7b` |
| Agents | `id` (custom string) | `claude-3` |

```python
# Projects use slug
PATCH /api/projects/website-redesign

# Tasks use hex ID
PATCH /api/tasks/4f59be5bdef1d782

# Pages use hex ID
PATCH /api/pages/cb6fb862de4bec7b
```

---

## Slug Auto-Generation

**Problem:** Project name with special characters generates unexpected slug.

```python
# Name → Slug mapping
"Marketing Campaign"    → "marketing-campaign"
"Sprint 42 / Q2"        → "sprint-42-q2"
"API (v2)"              → "api-v2"
"Café & Restaurant"     → "caf-restaurant"
"日本語テスト"           → "untitled" (non-latin → fallback)
```

**Tip:** If slug matters, provide it explicitly:
```python
api("POST", "/api/projects", {"name": "Sprint 42 / Q2", "slug": "sprint-42-q2"})
```

---

## Slug Collision

**Problem:** Creating a project with a name that matches an existing slug.

**Behavior:** AgentBoard auto-appends numeric suffix: `my-project-2`, `my-project-3`, etc.

```python
# If "website-redesign" already exists:
api("POST", "/api/projects", {"name": "Website Redesign"})
# Returns slug: "website-redesign-2"
```

**Edge case:** After 98 collisions, returns `409 SLUG_CONFLICT`.

---

## Setup Endpoint (One-Time Only)

**Problem:** Calling `POST /api/setup` after projects already exist.

```json
{"error": "Setup already completed — projects already exist", "code": "SETUP_DONE"}
```

**Solution:** Use `POST /api/projects` instead for additional projects.

---

## Soft Delete vs Hard Delete

**Problem:** Confusion about what DELETE actually does.

| Resource | DELETE behavior |
|----------|----------------|
| Projects | **Soft delete** — archived, data preserved |
| Tasks | **Hard delete** — permanently removed |
| Pages | **Hard delete** — cascade deletes children |

```python
# Archive project (recoverable)
DELETE /api/projects/my-project

# Restore archived project
POST /api/projects/my-project/restore

# Delete task (NOT recoverable!)
DELETE /api/tasks/{id}
```

---

## Auto-Timestamps

**Problem:** Manually setting `started_at` or `completed_at` — they're auto-managed.

```python
# DON'T set these manually — they're ignored or overridden
api("PATCH", f"/api/tasks/{id}", {"status": "in_progress", "started_at": "..."})

# DO let the server handle timestamps:
api("PATCH", f"/api/tasks/{id}", {"status": "in_progress"})   # auto-sets started_at
api("PATCH", f"/api/tasks/{id}", {"status": "done"})          # auto-sets completed_at
```

---

## Task Position Ordering

**Problem:** Tasks ordered by `position` within each status group.

```python
# New tasks are appended to end of their status group
# Position auto-calculated as MAX(position) + 1 for that status

# To reorder, update position:
api("PATCH", f"/api/tasks/{id}", {"position": 1.5})  # Insert between positions 1 and 2
```

---

## Content-Type Required

**Problem:** POST/PATCH without Content-Type returns unexpected errors.

```python
# WRONG
api("POST", "/api/projects", {"name": "test"})

# CORRECT — Content-Type must be set
req = Request(url, data=json.dumps(body).encode(),
              headers={"Authorization": f"Bearer {key}",
                       "Content-Type": "application/json"})
```

---

## Port Conflicts

**Problem:** Default port 8765 already in use.

**Solution:** Use CLI args or env vars to change port:

```bash
python3 server.py --port 8766
# or
AGENTBOARD_PORT=8766 python3 server.py
# or
AGENTBOARD_PORT=8766 AGENTBOARD_DB_PATH=agentboard-dev.db python3 server.py
```

---

## Database Lock (WAL Mode)

**Problem:** SQLite "database is locked" errors under concurrent access.

**Reality:** AgentBoard uses WAL mode, which handles concurrent reads well. Write contention is rare for typical agent use. If it occurs:

1. Wait and retry (WAL resolves quickly)
2. Check for long-running transactions
3. Ensure no other process is holding a write lock

---

## Import Data Validation

**Problem:** Importing malformed JSON or incompatible data.

```python
# Import validates:
# - JSON structure matches export format
# - Required fields present
# - Slug conflicts handled (auto-suffix)
# - Agent IDs merged (no duplicates)

# Safe pattern:
status, data = api("GET", "/api/export")  # Get clean export
# ... optionally modify ...
api("POST", "/api/import", data)           # Re-import
```

---

## FTS5 Search Limitations

**Problem:** Search doesn't find what you expect.

| Limitation | Example |
|-----------|---------|
| Minimum token length | "API" (3 chars) — may not match, try "application" |
| No fuzzy matching | "colmment" won't match "comment" |
| No partial matching | "landi" won't match "landing" |
| Porter stemming | "testing" matches "test", "tests" |

**Tip:** Use multiple search terms: `?q=design+mockup+landing` (OR semantics).
