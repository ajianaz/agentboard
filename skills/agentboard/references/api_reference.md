# AgentBoard API Reference

> Base URL: `http://127.0.0.1:8765/api`
> All responses: JSON. Error format: `{"error": "msg", "code": "ERROR_CODE"}`

### Authentication

| Request Type | Auth Required | Behavior |
|-------------|--------------|----------|
| `GET /api/*` | ❌ No (when `public_read=true`) | Browse freely |
| `POST /api/*` | ✅ Yes | Create resources |
| `PATCH /api/*` | ✅ Yes | Update resources |
| `DELETE /api/*` | ✅ Yes | Delete resources |
| `POST /api/setup` | ❌ No | First-run setup (always public) |
| `GET /api/auth/*` | ✅ Yes | Key management (always protected) |
| `GET /api/health` | ❌ No | Health check (always public) |
| Static files + `/` | ❌ No | SPA served always |

**Public read** is enabled by default (`auth.public_read = true`). To disable:
```bash
AGENTBOARD_PUBLIC_READ=false  # env var
# or in agentboard.toml: [auth] public_read = false
```

**Auth header format:** `Authorization: Bearer <api_key>` (read from `.api_key` file)

---

## Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List active projects |
| GET | `/api/projects?include_archived=1` | List including archived |
| GET | `/api/projects/{slug}` | Project detail + task stats |
| POST | `/api/projects` | Create project |
| PATCH | `/api/projects/{slug}` | Update project |
| DELETE | `/api/projects/{slug}` | Archive (soft delete) |
| POST | `/api/projects/{slug}/restore` | Unarchive |

**Create project:**
```json
{
  "name": "Marketing",
  "icon": "📊",
  "color": "#3b82f6",
  "description": "Content & distribution",
  "statuses": [
    {"key": "backlog", "label": "Backlog", "color": "#6b7280"},
    {"key": "draft", "label": "Draft", "color": "#f59e0b"},
    {"key": "review", "label": "Review", "color": "#8b5cf6"},
    {"key": "published", "label": "Published", "color": "#22c55e"}
  ]
}
```

---

## Tasks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{slug}/tasks` | Tasks in project |
| GET | `/api/projects/{slug}/tasks?status=review` | Filter by status |
| GET | `/api/projects/{slug}/tasks?assignee=cto` | Filter by agent |
| POST | `/api/projects/{slug}/tasks` | Create task |
| GET | `/api/tasks/{id}` | Get single task |
| PATCH | `/api/tasks/{id}` | Update task |
| DELETE | `/api/tasks/{id}` | Delete task |
| GET | `/api/tasks?project=all` | Cross-project all tasks |
| GET | `/api/tasks?project=all&status=review` | Cross-project filtered |

**Create task:**
```json
{
  "title": "Write launch email",
  "description": "Draft email for product launch",
  "status": "proposed",
  "priority": "high",
  "assignee": "kai",
  "tags": ["email", "launch"],
  "due_date": "2026-05-01",
  "created_by": "agent:kai",
  "parent_id": "abc12345"
}
```

> `parent_id` is optional — links this as a subtask of another task.

**Get subtasks:**
```
GET /api/tasks/{parent_id}/children
```

**HITL — Owner approve/reject:**
```json
// Approve
PATCH /api/tasks/{id} {"status": "todo", "comment": "Approved."}
// Reject
PATCH /api/tasks/{id} {"status": "rejected", "comment": "Not this week."}
```

---

## Pages (Documents)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{slug}/pages` | Page tree (nested) |
| POST | `/api/projects/{slug}/pages` | Create page |
| PATCH | `/api/pages/{id}` | Update page content |
| DELETE | `/api/pages/{id}` | Delete page |
| POST | `/api/pages/{id}/move` | Move page (parent/position) |

---

## Agents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents |
| GET | `/api/agents/{id}` | Get single agent |
| POST | `/api/agents` | Register agent |
| PATCH | `/api/agents/{id}` | Update agent profile |
| GET | `/api/agents/{id}/workload` | Agent's task statistics |

**Register agent:**
```json
{
  "id": "my-agent-id",
  "name": "My Agent",
  "role": "Content Writer",
  "avatar": "✍️",
  "color": "#f59e0b"
}
```

**Workload response:**
```json
{
  "agent_id": "cto",
  "agent_name": "CTO",
  "total": 5,
  "completed": 2,
  "by_status": {"todo": 1, "in_progress": 2, "review": 1, "done": 2},
  "active_projects": [{"id": "...", "name": "Hermes Fleet", "slug": "hermes-fleet"}]
}
```

---

## Comments

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks/{id}/comments` | Comments on task |
| POST | `/api/tasks/{id}/comments` | Add comment to task |
| GET | `/api/pages/{id}/comments` | Comments on page |
| POST | `/api/pages/{id}/comments` | Add comment to page |

**⚠️ NOTE:** Comments are **nested** under their target, NOT at `/api/comments`.
```json
POST /api/tasks/{task_id}/comments
{"author": "cto", "content": "Ready for review."}
```

---

## Activity

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/activity` | Recent activity (all projects) |
| GET | `/api/activity?project={slug}` | Activity for specific project |

---

## Search (FTS5)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/search?q={query}` | Search tasks + pages |
| GET | `/api/search?q={query}&project={slug}` | Search within project |

---

## Stats

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats` | Cross-project summary |

---

## Export / Import

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/export` | Export entire DB as JSON |
| GET | `/api/export?project={slug}` | Export single project |
| POST | `/api/import` | Import from JSON export |

**Import behavior:**
- Agents: upsert by `id`
- Projects: upsert by `slug` (metadata-only; tasks/pages appended)
- Tasks/Pages: always created new with fresh IDs
- Comments: always created new with remapped references

---

## Health Check

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Server health + maintenance status |

Response: `{"status": "ok", "maintenance": false}` (or `"status": "maintenance"` when enabled)

---

## Auth Keys (API Key Management)

All routes require auth (even with `public_read=true`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/keys` | List all keys (hashed) |
| POST | `/api/auth/keys` | Create key (raw shown once) |
| PATCH | `/api/auth/keys/{id}` | Update label, deactivate/activate |
| DELETE | `/api/auth/keys/{id}` | Delete key (blocks last active) |

**Create:** `POST /api/auth/keys {"label": "my-key"}` → `{"id": "...", "key": "ab_xxx...", "warning": "..."}`

**Deactivate:** `PATCH /api/auth/keys/{id} {"deactivate": true, "grace_minutes": 5}` — key works for 5 more minutes

**Activate:** `PATCH /api/auth/keys/{id} {"is_active": true}`

---

## Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `UNAUTHORIZED` | 401 | Missing/invalid API key |
| `FORBIDDEN` | 403 | Agent can't modify owner-only resources |
| `VALIDATION_ERROR` | 400 | Invalid request body |
| `SLUG_EXISTS` | 409 | Project slug already taken |
| `DB_ERROR` | 500 | Database operation failed |
| `MAINTENANCE` | 503 | Server in maintenance mode |
| `LAST_KEY` | 409 | Cannot delete last active API key |
