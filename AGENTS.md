# AGENTS.md — AgentBoard

> **This file is the single source of truth for any AI agent working with AgentBoard.**
> Read this file → you know everything needed to use, develop, and contribute.

## What is AgentBoard?

AgentBoard is a **standalone, multi-project task board** designed for human+AI collaboration.

- **Zero dependencies** — `git clone && python server.py` → works
- **Single SQLite file** — all data in `agentboard.db`
- **Vanilla HTML/CSS/JS frontend** — no build step, no npm, no framework
- **Python stdlib backend** — `http.server` only, no Flask/FastAPI
- **Agent-native** — agents read AGENTS.md and immediately know how to interact via API
- **HITL (Human-In-The-Loop)** — owner approves agent proposals via dashboard

## Quick Start

```bash
git clone https://github.com/ajianaz/agentboard.git
cd agentboard
python server.py
# Open http://localhost:8765
```

First run creates `agentboard.db` with default schema, one default project, and admin setup page.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   index.html (SPA)                   │
│         Vanilla JS, dark theme, responsive           │
│  ┌─────────┬────────────────────────────────────┐  │
│  │ Sidebar │  Main Content Area                  │  │
│  │         │  ┌──────────┬──────────┬──────────┐ │  │
│  │ Overview│  │  Board   │  Docs    │  Stats   │ │  │
│  │ Project │  │  (kanban)│  (tree)  │  (chart) │ │  │
│  │ List    │  └──────────┴──────────┴──────────┘ │  │
│  │ Agents  │                                      │  │
│  │ Settings│                                      │  │
│  └─────────┴──────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
         │ fetch() API calls (JSON)
         ▼
┌──────────────────────────────────────────────────────┐
│              server.py (Python stdlib)                │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐  │
│  │ Router │ │  Auth  │ │  API   │ │  Static    │  │
│  │        │ │ Module │ │Routes  │ │  Server    │  │
│  └────────┘ └────────┘ └────────┘ └────────────┘  │
│         │                                           │
│         ▼                                           │
│  ┌──────────────────────────────────────────────┐  │
│  │            agentboard.db (SQLite WAL)         │  │
│  │  projects │ tasks │ pages │ agents │ activity  │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## File Structure

```
agentboard/
├── server.py              # Entry point, HTTP server, routing
├── db.py                  # SQLite schema, migrations, queries
├── auth.py                # API key auth, session management
├── api/
│   ├── __init__.py
│   ├── projects.py        # Project CRUD
│   ├── tasks.py           # Task CRUD + cross-project queries
│   ├── pages.py           # Document tree CRUD
│   ├── agents.py          # Agent management
│   ├── comments.py        # Task/page comments
│   ├── activity.py        # Activity log
│   └── search.py          # FTS5 search
├── static/
│   └── index.html         # Single-page application (all UI)
├── agentboard.db          # SQLite database (auto-created)
├── config.yaml            # Optional config (all defaults work)
├── AGENTS.md              # THIS FILE
├── README.md
├── LICENSE                # Apache 2.0
├── NOTICE
├── CONTRIBUTING.md
├── docs/
│   └── plans/             # Implementation plans
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       └── ci.yml
└── tests/
    ├── test_db.py
    ├── test_api_projects.py
    ├── test_api_tasks.py
    ├── test_api_pages.py
    └── test_auth.py
```

## Database Schema

### Projects (dynamic, owner-managed)

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    icon TEXT DEFAULT '📋',
    color TEXT DEFAULT '#3b82f6',
    position INTEGER DEFAULT 0,
    statuses TEXT DEFAULT '[{"key":"proposed","label":"Proposed","color":"#f59e0b"},{"key":"todo","label":"To Do","color":"#6b7280"},{"key":"in_progress","label":"In Progress","color":"#3b82f6"},{"key":"review","label":"Review","color":"#8b5cf6"},{"key":"done","label":"Done","color":"#22c55e"}]',
    priorities TEXT DEFAULT '[{"key":"critical","label":"Critical","color":"#ef4444"},{"key":"high","label":"High","color":"#f97316"},{"key":"medium","label":"Medium","color":"#eab308"},{"key":"low","label":"Low","color":"#22c55e"},{"key":"none","label":"None","color":"#6b7280"}]',
    tags TEXT DEFAULT '[]',
    is_archived INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

**Key:** `statuses`, `priorities`, `tags` are JSON arrays — each project can customize its workflow.

### Tasks

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo',
    priority TEXT DEFAULT 'none',
    assignee TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    position REAL DEFAULT 0,
    due_date TEXT,
    started_at TEXT,
    completed_at TEXT,
    metadata TEXT DEFAULT '{}',
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assignee ON tasks(assignee);
```

### Pages (Outline-style documents)

```sql
CREATE TABLE pages (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES pages(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Untitled',
    content TEXT DEFAULT '',
    icon TEXT DEFAULT '📄',
    position REAL DEFAULT 0,
    depth INTEGER DEFAULT 0,
    is_expanded INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_pages_project ON pages(project_id);
CREATE INDEX idx_pages_parent ON pages(parent_id);
```

### Agents

```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT DEFAULT '',
    avatar TEXT DEFAULT '🤖',
    color TEXT DEFAULT '#3b82f6',
    is_active INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);
```

### Comments

```sql
CREATE TABLE comments (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    target_type TEXT NOT NULL CHECK(target_type IN ('task', 'page')),
    target_id TEXT NOT NULL,
    author TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_comments_target ON comments(target_type, target_id);
```

### Activity Log

```sql
CREATE TABLE activity (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT REFERENCES projects(id),
    target_type TEXT NOT NULL,
    target_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    detail TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_activity_project ON activity(project_id);
CREATE INDEX idx_activity_created ON activity(created_at DESC);
```

### FTS5 Search

```sql
CREATE VIRTUAL TABLE tasks_fts USING fts5(
    title, description,
    content=tasks,
    content_rowid=rowid,
    tokenize='porter unicode61'
);
-- Triggers auto-sync tasks → tasks_fts

CREATE VIRTUAL TABLE pages_fts USING fts5(
    title, content,
    content=pages,
    content_rowid=rowid,
    tokenize='porter unicode61'
);
```

## API Reference

All API endpoints return JSON. Auth via `Authorization: Bearer <api_key>` header.

### Base URL
`http://localhost:8765/api`

### Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List all active projects |
| GET | `/api/projects?include_archived=1` | List including archived |
| GET | `/api/projects/{slug}` | Get project detail + stats |
| POST | `/api/projects` | Create project |
| PATCH | `/api/projects/{slug}` | Update project |
| DELETE | `/api/projects/{slug}` | Archive project |
| POST | `/api/projects/{slug}/restore` | Unarchive |

**Create project body:**
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

### Tasks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{slug}/tasks` | Tasks in project |
| GET | `/api/projects/{slug}/tasks?status=review` | Filter by status |
| GET | `/api/projects/{slug}/tasks?assignee=cto` | Filter by agent |
| POST | `/api/projects/{slug}/tasks` | Create task |
| PATCH | `/api/tasks/{id}` | Update task |
| DELETE | `/api/tasks/{id}` | Delete task |
| GET | `/api/tasks?project=all` | Cross-project tasks |
| GET | `/api/tasks?project=all&status=review` | Cross-project filter |

**Create task body:**
```json
{
  "title": "Write launch email",
  "description": "Draft email for product launch",
  "status": "todo",
  "priority": "high",
  "assignee": "kai",
  "tags": ["email", "launch"],
  "due_date": "2026-05-01"
}
```

### HITL (Human-In-The-Loop)

**Agent creates task with `status: "proposed"`:**
```json
POST /api/projects/marketing/tasks
{
  "title": "Create social media calendar",
  "description": "Plan content for next 2 weeks",
  "status": "proposed",
  "priority": "high",
  "assignee": "kai",
  "created_by": "agent:kai"
}
```

**Owner approves (via dashboard or API):**
```json
PATCH /api/tasks/{id}
{
  "status": "todo",
  "comment": "Approved. Focus on Instagram first."
}
```

**Owner rejects:**
```json
PATCH /api/tasks/{id}
{
  "status": "rejected",
  "comment": "Not this week. We're focusing on launch."
}
```

### Pages

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{slug}/pages` | Page tree (nested) |
| POST | `/api/projects/{slug}/pages` | Create page |
| PATCH | `/api/pages/{id}` | Update page |
| DELETE | `/api/pages/{id}` | Delete page |
| POST | `/api/pages/{id}/move` | Move page (change parent/position) |

### Agents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents |
| POST | `/api/agents` | Register agent |
| PATCH | `/api/agents/{id}` | Update agent |
| GET | `/api/agents/{id}/workload` | Agent's task stats |

### Activity

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/activity` | Recent activity (all projects) |
| GET | `/api/activity?project={slug}` | Activity for project |
| GET | `/api/stats` | Cross-project summary |

### Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/search?q={query}` | Search tasks + pages |
| GET | `/api/search?q={query}&project={slug}` | Search within project |

## Agent Workflow

### For AI agents reading this:

**1. Register yourself on first use:**
```bash
curl -X POST http://localhost:8765/api/agents \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id": "my-agent-id", "name": "My Agent", "role": "Content Writer"}'
```

**2. Find your tasks:**
```bash
curl http://localhost:8765/api/tasks?project=all&assignee=my-agent-id \
  -H "Authorization: Bearer $API_KEY"
```

**3. Create a task (proposed → needs owner approval):**
```bash
curl -X POST http://localhost:8765/api/projects/{slug}/tasks \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Task title",
    "description": "What this task accomplishes",
    "status": "proposed",
    "priority": "medium",
    "assignee": "my-agent-id",
    "created_by": "agent:my-agent-id"
  }'
```

**4. Update task progress:**
```bash
curl -X PATCH http://localhost:8765/api/tasks/{id} \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'
```

**5. Submit for review when done:**
```bash
curl -X PATCH http://localhost:8765/api/tasks/{id} \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "review", "comment": "Ready for review. See attached docs."}'
```

**6. Check for feedback:**
```bash
curl http://localhost:8765/api/tasks/{id} \
  -H "Authorization: Bearer $API_KEY"
# Look at comments array for owner feedback
```

### Task Lifecycle

```
┌──────────┐    agent creates     ┌──────────┐
│          │ ──────────────────→  │          │
│          │    owner approves    │          │
│          │ ←──────────────────  │          │
│          │                      │          │
│ proposed │ ──────────────────→  │   todo   │
│          │                      │          │
└──────────┘                      └────┬─────┘
                                       │ agent starts
                                       ▼
                                  ┌──────────┐
                                  │in_progress│
                                  └────┬─────┘
                                       │ agent submits
                                       ▼
                                  ┌──────────┐
                                  │  review  │ ← owner reviews
                                  └────┬─────┘
                                       │
                          ┌────────────┼────────────┐
                          │ approved   │ rejected   │
                          ▼            ▼            │
                     ┌────────┐  ┌─────────┐        │
                     │  done  │  │rejected │────────┘
                     └────────┘  │(feedback│  agent revises
                                  │→ back to│
                                  │in_prog) │
                                  └─────────┘
```

## Configuration

`config.yaml` is optional. All values have defaults:

```yaml
server:
  host: "0.0.0.0"
  port: 8765
  
database:
  path: "agentboard.db"
  
auth:
  # Generated on first run if not set
  api_key: ""
  
defaults:
  project:
    name: "My Project"
    statuses:
      - key: proposed
        label: Proposed
        color: "#f59e0b"
      - key: todo
        label: To Do
        color: "#6b7280"
      - key: in_progress
        label: In Progress
        color: "#3b82f6"
      - key: review
        label: Review
        color: "#8b5cf6"
      - key: done
        label: Done
        color: "#22c55e"
```

## Development

```bash
# Run dev server (auto-reload on file change)
python server.py --dev

# Run tests
python -m pytest tests/ -v

# Run single test
python -m pytest tests/test_api_tasks.py -v
```

## Conventions

- **IDs:** 16-char lowercase hex (`lower(hex(randomblob(8)))`)
- **Timestamps:** ISO 8601 UTC (`datetime('now')` in SQLite)
- **JSON columns:** `statuses`, `priorities`, `tags`, `metadata` — always valid JSON
- **Slug generation:** lowercase, hyphens replace spaces, strip special chars
- **Soft delete:** `is_archived = 1` for projects, never hard delete
- **Auth:** Bearer token in `Authorization` header
- **Error responses:** `{"error": "message", "code": "ERROR_CODE"}` with appropriate HTTP status

## Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `UNAUTHORIZED` | 401 | Missing/invalid API key |
| `FORBIDDEN` | 403 | Agent can't modify owner-only resources |
| `VALIDATION_ERROR` | 400 | Invalid request body |
| `SLUG_EXISTS` | 409 | Project slug already taken |
| `DB_ERROR` | 500 | Database operation failed |

## Testing

```bash
# All tests use in-memory SQLite (:memory:)
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

## License

Apache 2.0 — see LICENSE file.
