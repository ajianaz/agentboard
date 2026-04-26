# AgentBoard API Reference

Complete reference for all 31 API endpoints. Base URL: `http://localhost:8765`

## Authentication

All `/api/*` endpoints require `Authorization: Bearer <api_key>` header.

```
Authorization: Bearer ab_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Get your key from `.api_key` file (auto-generated on first run) or set `AGENTBOARD_API_KEY` env var.

Exception: `POST /api/setup` works without auth (one-time only).

---

## Projects (7 endpoints)

### `GET /api/projects`
List all active projects.

**Query params:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `include_archived` | `0` or `1` | `0` | Include archived projects |

**Response:** `{"projects": [...], "total": N}`

### `GET /api/projects/{slug}`
Get project detail with stats.

**Response:** `{"project": {...}, "stats": {"total_tasks": N, "done_tasks": N, ...}}`

### `POST /api/projects`
Create a new project.

**Body:**
```json
{
  "name": "My Project (required)",
  "slug": "custom-slug (optional, auto-generated from name)",
  "description": "...",
  "icon": "📋",
  "color": "#3b82f6",
  "statuses": [{"key": "todo", "label": "To Do", "color": "#6b7280"}],
  "priorities": [{"key": "high", "label": "High", "color": "#f97316"}],
  "tags": ["tag1", "tag2"]
}
```

**Response:** `201 {"project": {...}}`

Default statuses: `proposed`, `todo`, `in_progress`, `review`, `done`
Default priorities: `critical`, `high`, `medium`, `low`, `none`

### `PATCH /api/projects/{slug}`
Update project fields. Send only fields to update.

**Body:** Same as POST (partial allowed)

**Response:** `{"project": {...}}`

### `DELETE /api/projects/{slug}`
Archive project (soft delete). Tasks and pages are preserved.

**Response:** `{"project": {...}}`

### `POST /api/projects/{slug}/restore`
Unarchive a previously archived project.

**Response:** `{"project": {...}}`

### `GET /api/stats`
Cross-project summary statistics.

**Response:**
```json
{
  "total_tasks": 42,
  "done_tasks": 15,
  "proposed_tasks": 3,
  "in_progress_tasks": 10,
  "review_tasks": 5,
  "completion_pct": 35.7,
  "projects": [...]
}
```

---

## Tasks (8 endpoints)

### `GET /api/projects/{slug}/tasks`
List tasks in a project.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by status (e.g. `todo`, `in_progress`) |
| `assignee` | string | Filter by assignee ID/name |
| `priority` | string | Filter by priority |

**Response:** `{"tasks": [...], "total": N}`

### `POST /api/projects/{slug}/tasks`
Create a task in a project.

**Body:**
```json
{
  "title": "Task title (required)",
  "description": "...",
  "status": "proposed",
  "priority": "medium",
  "assignee": "agent-name",
  "tags": ["frontend", "bug"],
  "due_date": "2026-05-01"
}
```

**Response:** `201 {"task": {...}}`

Auto-timestamps: `started_at` set when status=`in_progress`, `completed_at` set when status=`done`.

### `PATCH /api/tasks/{id}`
Update a task. Send only fields to update.

**Body:**
```json
{
  "title": "New title",
  "status": "done",
  "description": "Updated description"
}
```

**Response:** `{"task": {...}}`

### `DELETE /api/tasks/{id}`
Permanently delete a task.

**Response:** `{"deleted": true, "id": "..."}`

### `GET /api/tasks/{id}`
Get single task detail.

**Response:** `{"task": {...}}`

### `GET /api/tasks`
Cross-project task query.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `project` | string | Project slug, or `all` for cross-project |
| `assignee` | string | Filter by assignee |
| `status` | string | Filter by status |

**Response:** `{"tasks": [...], "total": N}`

---

## Pages (5 endpoints)

Pages are Outline-style documents with recursive nesting via `parent_id`.

### `GET /api/projects/{slug}/pages`
Get page tree for a project (nested).

**Response:** `{"pages": [...], "total": N}`

### `POST /api/projects/{slug}/pages`
Create a page.

**Body:**
```json
{
  "title": "Page title",
  "content": "Markdown content...",
  "icon": "📄",
  "parent_id": null,
  "position": 0
}
```

**Response:** `201 {"page": {...}}`

### `PATCH /api/pages/{id}`
Update page content or metadata.

**Body:**
```json
{
  "title": "Updated title",
  "content": "Updated content"
}
```

**Response:** `{"page": {...}}`

### `DELETE /api/pages/{id}`
Delete page and all children (cascade).

**Response:** `{"deleted": true}`

### `POST /api/pages/{id}/move`
Move page to new parent or position.

**Body:**
```json
{
  "parent_id": "new-parent-id or null",
  "position": 2
}
```

**Response:** `{"page": {...}}`

---

## Agents (4 endpoints)

### `GET /api/agents`
List all registered agents.

**Response:** `{"agents": [...]}`

### `POST /api/agents`
Register a new agent.

**Body:**
```json
{
  "id": "claude-3",
  "name": "Claude 3",
  "role": "Code Reviewer",
  "avatar": "🤖",
  "color": "#8b5cf6"
}
```

**Response:** `201 {"agent": {...}}`

### `PATCH /api/agents/{id}`
Update agent info.

**Response:** `{"agent": {...}}`

### `GET /api/agents/{id}/workload`
Get agent's task statistics across all projects.

**Response:**
```json
{
  "agent": {...},
  "workload": {
    "total": 12,
    "by_status": {"todo": 3, "in_progress": 5, "review": 2, "done": 2},
    "by_project": [{"project": "...", "count": 5}]
  }
}
```

---

## Comments (4 endpoints)

### `GET /api/tasks/{id}/comments`
List comments on a task.

**Response:** `{"comments": [...]}`

### `POST /api/tasks/{id}/comments`
Add comment to a task.

**Body:**
```json
{
  "content": "Comment text (required)",
  "author": "agent-name (optional, defaults to 'owner')"
}
```

**Response:** `201 {"comment": {...}}`

### `GET /api/pages/{id}/comments`
List comments on a page.

### `POST /api/pages/{id}/comments`
Add comment to a page. Same body as task comment.

---

## Activity & Stats (1 endpoint)

### `GET /api/activity`
Recent activity feed.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `project` | string | Filter by project slug |
| `limit` | int | Max results (default: 50) |

**Response:** `{"activity": [...]}`

---

## Search (1 endpoint)

### `GET /api/search?q={query}`
FTS5 full-text search across tasks and pages.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Search query (required) |
| `project` | string | Limit to project slug |

**Response:**
```json
{
  "results": [
    {"type": "task", "id": "...", "title": "...", "project": "...", "snippet": "..."},
    {"type": "page", "id": "...", "title": "...", "project": "...", "snippet": "..."}
  ],
  "total": N
}
```

---

## Export / Import (2 endpoints)

### `GET /api/export`
Export all data as JSON.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `project` | string | Export single project (omit for all) |

**Response:**
```json
{
  "version": 1,
  "exported_at": "2026-04-26T01:00:00Z",
  "projects": [...],
  "agents": [...]
}
```

### `POST /api/import`
Import data from JSON export.

**Body:** Same format as export response.

**Response:** `{"imported": {"projects": N, "tasks": N, "pages": N, "agents": N}}`

---

## Setup (1 endpoint)

### `POST /api/setup`
One-time initial setup. Creates the first project. **Can only be called once.**

**Body:**
```json
{
  "name": "My First Project",
  "description": "Optional description"
}
```

**Response:** `201 {"project": {...}}`

Returns `400 {"code": "SETUP_DONE"}` if projects already exist.

---

## Error Responses

All errors follow this format:

```json
{"error": "Human-readable message", "code": "ERROR_CODE"}
```

| Code | HTTP | Meaning |
|------|------|---------|
| `VALIDATION_ERROR` | 400 | Missing or invalid input |
| `SETUP_DONE` | 400 | Setup already completed |
| `UNAUTHORIZED` | 401 | Missing or invalid API key |
| `NOT_FOUND` | 404 | Resource not found |
| `SLUG_CONFLICT` | 409 | Duplicate slug |

---

## Special Headers

| Header | Description |
|--------|-------------|
| `Authorization` | `Bearer <api_key>` — required for all `/api/*` |
| `X-Actor` | Agent name — used as `created_by` in activity logs |
| `Content-Type` | `application/json` — required for POST/PATCH |
