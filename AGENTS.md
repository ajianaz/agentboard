# AGENTS.md — AgentBoard

> **This file is the single source of truth for any AI agent working with AgentBoard.**
> Read this file → you know everything needed to use, develop, and contribute.

## What is AgentBoard?

AgentBoard is a **standalone, multi-project task board** designed for human+AI collaboration.

- **Zero dependencies** — `git clone && python server.py` → works
- **Zero pip install** — Python 3.11+ stdlib only (`tomllib`, `http.server`)
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

First run creates `agentboard.db` with default schema (v6), imports legacy API key, starts KPI engine, and runs auto-cleanup.

**CLI flags** (optional, override everything):
```bash
python server.py --port 9000 --host 127.0.0.1 --log
python server.py --config /path/to/custom.toml
```

## Agent Skill

This repository includes a **ready-to-use agent skill** in `skills/agentboard/`. Any AI agent that clones this repo can immediately interact with the board via API.

**Quick setup for agents:**
```bash
# 1. Read the skill
cat skills/agentboard/SKILL.md

# 2. Get API key
KEY=$(cat .api_key)

# 3. Start interacting
curl -H "Authorization: Bearer $KEY" http://localhost:8765/api/stats
```

**Skill contents:**
| File | Purpose |
|------|---------|
| [`skills/agentboard/SKILL.md`](skills/agentboard/SKILL.md) | Hub — triggers, quick reference, rules |
| [`skills/agentboard/references/api_reference.md`](skills/agentboard/references/api_reference.md) | All 31 endpoints documented |
| [`skills/agentboard/references/code_examples.md`](skills/agentboard/references/code_examples.md) | Python & curl snippets |
| [`skills/agentboard/references/workflows.md`](skills/agentboard/references/workflows.md) | HITL, reporting, backup workflows |
| [`skills/agentboard/references/pitfalls.md`](skills/agentboard/references/pitfalls.md) | Gotchas and troubleshooting |

The skill is self-contained — no installation, no dependencies. Just read `SKILL.md` and start using the API.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   index.html (SPA)                   │
│         Vanilla JS, dark theme, responsive           │
│  ┌─────────┬────────────────────────────────────┐  │
│  │ Sidebar │  Main Content Area                  │  │
│  │         │  ┌──────────┬──────────┬──────────┐ │  │
│  Overview│  │  Board   │  Docs    │  Stats   │ │  │
│  Project │  │  (kanban)│  (tree)  │  (chart) │ │  │
│  List    │  └──────────┴──────────┴──────────┘ │  │
│  Agents  │  ┌──────────┬──────────┬──────────┐ │  │
│  Settings│  │Analytics │Discussions│Activity │ │  │
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
│  ┌──────────────────────────────────────────────┐  │
│  │  config.py — agentboard.toml loader (tomllib) │  │
│  │  CLI args > env vars > TOML > defaults       │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  kpi_engine.py — Background KPI computation    │  │
│  │  activity_logger.py — Auto-logging middleware   │  │
│  └──────────────────────────────────────────────┘  │
│         │                                           │
│         ▼                                           │
│  ┌──────────────────────────────────────────────┐  │
│  │            agentboard.db (SQLite WAL)         │  │
│  │  projects │ tasks │ pages │ agents │ activity │ api_keys │
│  │  kpi_daily │ kpi_weekly │ discussions │ discussion_feedback │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## File Structure

```
agentboard/
├── server.py              # Entry point, HTTP server, routing
├── config.py              # Configuration loader (agentboard.toml, tomllib)
├── db.py                  # SQLite schema v5, migrations, WAL mode, retention
├── auth.py                # API key auth, session management
├── kpi_engine.py          # Background KPI computation engine
├── activity_logger.py     # Auto-logging middleware for write operations
├── onboard.py             # First-run setup + sample data generation
├── api/
│   ├── __init__.py
│   ├── projects.py        # Project CRUD
│   ├── tasks.py           # Task CRUD + cross-project queries
│   ├── pages.py           # Document tree CRUD
│   ├── agents.py          # Agent management
│   ├── comments.py        # Task/page comments
│   ├── activity.py        # Activity log (enhanced with filters)
│   ├── analytics.py       # KPI metrics, trends, export, recompute
│   ├── discussions.py     # Multi-round discussion/review system
│   ├── search.py          # FTS5 search
│   ├── export.py          # Export/import endpoints
│   └── auth_keys.py        # API key CRUD & rotation
├── static/
│   └── index.html         # Single-page application (all UI)
├── tests/
│   ├── conftest.py        # Shared pytest fixtures (db_conn, api_key)
│   ├── test_db.py         # Schema, tables, FTS5, gen_id, slugify (7 tests)
│   └── test_auth.py       # Key gen, hashing, validation, header parsing (10 tests)
├── skills/
│   └── agentboard/       # Agent integration skill
│       ├── SKILL.md      # Skill hub — read this first
│       └── references/
│           ├── api_reference.md    # All 40+ API endpoints
│           ├── code_examples.md    # Python & curl snippets
│           ├── workflows.md        # Common agent workflows (incl. discussion)
│           └── pitfalls.md         # Gotchas & troubleshooting
├── tools/
│   ├── __init__.py
│   ├── client.py            # Python client wrapper (Board class)
│   ├── discussion.py        # Discussion coordinator (DiscussionSession)
│   └── README.md            # Tools documentation
├── agentboard.db          # SQLite database (auto-created, gitignored)
├── agentboard.toml        # Optional config (all defaults work)
├── .api_key               # Auto-generated API key (first run, gitignored)
├── .env                   # Production env vars (NOT committed, gitignored)
├── .env.example           # Template for .env
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Docker deployment (bind mount, env_file)
├── .dockerignore          # Docker build exclusions
├── AGENTS.md              # THIS FILE
├── README.md
├── LICENSE                # Apache 2.0
├── NOTICE
├── CONTRIBUTING.md
├── docs/
│   └── plans/             # Implementation plans
└── .github/
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    ├── PULL_REQUEST_TEMPLATE.md
    └── workflows/
        ├── ci.yml                # pytest matrix (3.11, 3.12, 3.13)
        └── docker-publish.yml    # Multi-arch build → ghcr.io
```

## Docker Deployment

AgentBoard supports Docker as an **optional** deployment method. Standalone (`python server.py`) is always the primary approach.

### Production Setup

```bash
# 1. Clone to deployment directory
git clone https://github.com/ajianaz/agentboard.git ~/agentboard
cd ~/agentboard

# 2. Create env file
cp .env.example .env
# Edit .env — set AGENTBOARD_API_KEY (or leave empty for auto-gen)

# 3. Start
docker compose up -d
```

### Key Docker Details

| Aspect | Detail |
|--------|--------|
| **Image** | `ghcr.io/ajianaz/agentboard:latest` (main) or `:develop` (dev) |
| **WORKDIR** | `/app` |
| **Data persistence** | Bind mount `.:/app` — DB, API key, config survive restarts |
| **Healthcheck** | `python3 -c "import urllib.request; ..."` (zero-dep, no curl needed) |
| **Env config** | `env_file: ./.env` — all vars optional, see `.env.example` |
| **Reverse proxy** | Traefik labels commented in docker-compose.yml — uncomment for public deployment |
| **Multi-arch** | amd64 + arm64 native builds (no QEMU emulation) |

### Bind Mount Pattern

The bind mount `.:/app` maps the host directory 1:1 to the container WORKDIR:

```
Host (~/agentboard/)           Container (/app/)
├── .env                         ├── .env          ← env vars
├── agentboard.db                ├── agentboard.db ← SQLite data
├── .api_key                     ├── .api_key      ← auth key
└── agentboard.toml              └── agentboard.toml ← optional config
```

This means all runtime data is on the host filesystem — no Docker volumes needed.

### Docker Compose (excerpt)

```yaml
services:
  agentboard:
    image: ghcr.io/ajianaz/agentboard:latest
    env_file: ./.env
    volumes:
      - .:/app
    ports:
      - "8765:8765"
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8765/')"]
      interval: 30s
      timeout: 5s
      retries: 3
    # Uncomment for Traefik reverse proxy:
    # networks:
    #   - public-net
    # labels:
    #   - "traefik.enable=true"
    #   - "traefik.http.routers.agentboard.rule=Host(`board.example.com`)"
    #   - "traefik.http.services.agentboard.loadbalancer.server.port=8765"
```

## Development Environment (Side-by-Side with Production)

For live production systems, always develop in a separate clone to avoid
affecting production data:

```bash
# Production (DO NOT modify directly for development)
~/agentboard/               ← running, has real data

# Development (separate clone)
git clone -b develop https://github.com/ajianaz/agentboard.git ~/agentboard-dev
cd ~/agentboard-dev

# Dev uses different port and DB automatically
AGENTBOARD_PORT=8766 AGENTBOARD_DB_PATH=agentboard-dev.db python3 server.py
# → http://127.0.0.1:8766
```

### Isolation Guarantees

| Resource | Production | Development |
|----------|-----------|-------------|
| Directory | `~/agentboard/` | `~/agentboard-dev/` |
| Port | 8765 (default) | 8766 (or any free port) |
| Database | `agentboard.db` | `agentboard-dev.db` |
| API Key | `.api_key` | `.api_key` (auto-generated) |

### Deploy Workflow

```bash
# 1. Develop and test in ~/agentboard-dev
# 2. Push to develop → CI passes → merge to main
# 3. In production:
cd ~/agentboard
git pull                          # Update code (DB untouched)
docker compose restart            # Or: python3 server.py
# 4. Verify: check health endpoint and dashboard
```

### Rollback

```bash
cd ~/agentboard
git checkout v1.0.0               # Pin to known-good version
docker compose restart
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

### Discussions (multi-round review)

```sql
CREATE TABLE discussions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    title TEXT NOT NULL,
    target_type TEXT DEFAULT '',
    target_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open',          -- open, closed, consensus
    current_round INTEGER DEFAULT 1,
    max_rounds INTEGER DEFAULT 5,
    created_by TEXT DEFAULT '',
    context TEXT DEFAULT '',              -- background/context for the discussion
    participants TEXT DEFAULT '[]',       -- JSON array of participant IDs
    leader TEXT DEFAULT '',               -- discussion leader/organizer
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_discussions_target ON discussions(target_type, target_id);
CREATE INDEX idx_discussions_status ON discussions(status);
CREATE INDEX idx_discussions_created ON discussions(created_at DESC);
```

```sql
CREATE TABLE discussion_feedback (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    discussion_id TEXT NOT NULL REFERENCES discussions(id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    participant TEXT NOT NULL,
    role TEXT DEFAULT '',
    verdict TEXT DEFAULT '',              -- approve, conditional, reject, or empty
    content TEXT NOT NULL DEFAULT '',
    word_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_feedback_discussion ON discussion_feedback(discussion_id);
CREATE INDEX idx_feedback_round ON discussion_feedback(discussion_id, round);
CREATE INDEX idx_feedback_participant ON discussion_feedback(discussion_id, participant);
```


### API Keys (multi-key auth, schema v3)

```sql
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    key_hash TEXT NOT NULL UNIQUE,
    label TEXT DEFAULT 'default',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_used_at TEXT,
    grace_until TEXT
);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);
```

**Key rotation:** Keys are stored hashed (SHA-256). Raw keys are shown only once on creation. Deactivated keys can have a grace period (configurable minutes) during which they still authenticate. The last active key cannot be deleted.

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

All API endpoints return JSON.

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

**Public read** is enabled by default. Write operations require: `Authorization: Bearer <api_key>`

To disable public read: `AGENTBOARD_PUBLIC_READ=false` or `[auth] public_read = false` in `agentboard.toml`.

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

### Export / Import

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/export` | Export entire database as JSON |
| GET | `/api/export?project={slug}` | Export single project |
| POST | `/api/import` | Import data from JSON export |

**Export response format (v1):**
```json
{
  "version": 1,
  "exported_at": "2026-04-25T16:00:00+00:00",
  "projects": [
    {
      "id": "abc123...",
      "name": "Marketing",
      "slug": "marketing",
      "description": "",
      "icon": "📊",
      "color": "#3b82f6",
      "statuses": [...],
      "priorities": [...],
      "tags": [...],
      "tasks": [
        {
          "id": "def456...",
          "title": "Write launch email",
          "status": "todo",
          "priority": "high",
          "assignee": "kai",
          "tags": ["email"],
          ...
        }
      ],
      "pages": [
        {
          "id": "ghi789...",
          "title": "Brand Guidelines",
          "content": "...",
          "parent_id": null,
          "depth": 0,
          ...
        }
      ],
      "comments": [
        {
          "id": "jkl012...",
          "target_type": "task",
          "target_id": "def456...",
          "author": "owner",
          "content": "Looks good!",
          "created_at": "..."
        }
      ],
      "activity": [...]
    }
  ],
  "agents": [
    {
      "id": "agent-kai",
      "name": "Kai",
      "role": "Content Writer",
      "avatar": "🤖",
      ...
    }
  ]
}
```

**Import request:**
```json
POST /api/import
{
  "data": { ...export format above... }
}
```

**Import behavior:**
- **Agents:** upsert by `id` (existing agents are updated, new ones are created)
- **Projects:** upsert by `slug` (existing projects are updated metadata-only; tasks/pages are always appended)
- **Tasks:** always created new with fresh IDs
- **Pages:** always created new with fresh IDs; `parent_id` references are remapped
- **Comments:** always created new; `target_id` references are remapped for tasks/pages

**Import response:**
```json
{
  "imported": {
    "projects": 2,
    "tasks": 15,
    "pages": 8,
    "agents": 3
  }
}
```

**Example — backup and restore:**
```bash
# Export everything
curl http://localhost:8765/api/export \
  -H "Authorization: Bearer <api-key>" > backup.json

# Import into a fresh instance
curl -X POST http://localhost:8765/api/import \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d "{\"data\": $(cat backup.json)}"
```


### Health Check

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Server health + maintenance status |

**Response:**
```json
{
  "status": "ok",
  "maintenance": false,
  "version": "1.1.0"
}
```

When maintenance mode is active:
```json
{
  "status": "maintenance",
  "maintenance": true,
  "version": "1.1.0"
}
```

### Discussions

Multi-round discussion/review system for structured agent collaboration.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/discussions` | List discussions (filter: `?status=open`, `?target_type=task`, `?target_id={id}`) |
| GET | `/api/discussions/{id}` | Discussion detail + all feedback |
| POST | `/api/discussions` | Create discussion |
| PATCH | `/api/discussions/{id}` | Update (status, title, round, context, leader, participants) |
| DELETE | `/api/discussions/{id}` | Delete + all feedback |
| POST | `/api/discussions/{id}/feedback` | Add/update feedback (verdict: approve/conditional/reject) |
| GET | `/api/discussions/{id}/summary` | Verdict summary + consensus status |

**Create discussion:**
```json
POST /api/discussions
{
  "title": "Architecture Decision — Auth Strategy",
  "target_type": "task",
  "target_id": "abc12345",
  "max_rounds": 3,
  "context": "We need to decide between JWT and session-based auth for the new product.",
  "leader": "cto",
  "participants": ["zeko", "bad-sector"],
  "created_by": "agent:cto"
}
```

**Submit feedback:**
```json
POST /api/discussions/{id}/feedback
{
  "participant": "zeko",
  "role": "Security Specialist",
  "verdict": "conditional",
  "content": "JWT is the right choice, but we need refresh token rotation. See section 3.",
  "round": 1
}
```

**Close discussion:**
```json
PATCH /api/discussions/{id} {"status": "closed"}
```

**Discussion lifecycle:**
```
open → consensus  (all participants approve)
open → closed     (manually closed by leader)
```

**Consensus values:** `approved`, `rejected`, `approved_with_conditions`, `in_progress`, `no_feedback`

**Coordinator script** (`tools/discussion.py`):
```python
from tools.discussion import DiscussionSession

disc = DiscussionSession(
    topic="Auth Strategy Review",
    leader="cto",
    participants=["zeko", "bad-sector"],
    phase="concept",
    max_rounds=2
)
disc.create()
disc.write_leader_draft("# Draft\n\n...")
disc.send_round_request(send_fn=my_webhook_sender)
feedback = disc.collect_feedback(timeout=120)
disc.write_synthesis("# Synthesis\n\n...")
disc.close()
```

### Auth Keys (API Key Management)

All `/api/auth/*` routes **always require authentication** (even when `public_read=true`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/keys` | List all keys (hashed, never raw) |
| POST | `/api/auth/keys` | Create new key (raw key shown once) |
| PATCH | `/api/auth/keys/{id}` | Update label, deactivate/activate |
| DELETE | `/api/auth/keys/{id}` | Delete key (blocks last active) |

**Create key:**
```json
POST /api/auth/keys
{"label": "claude-code"}
// Response (raw key shown ONLY here):
{"id": "abc...", "label": "claude-code", "key": "ab_xxx...", "warning": "Save this key now — it cannot be retrieved again."}
```

**Deactivate with grace period:**
```json
PATCH /api/auth/keys/{id}
{"deactivate": true, "grace_minutes": 5}
// Key continues to work for 5 minutes, then is fully rejected
```

**Activate:**
```json
PATCH /api/auth/keys/{id}
{"is_active": true}
```

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

Configuration is managed by `config.py` using Python 3.11+ stdlib `tomllib`. **Fully optional** — AgentBoard works with zero config files using built-in defaults.

### Priority Hierarchy (highest wins)

1. **CLI arguments** — `--port`, `--host`, `--config`, `--log`
2. **Environment variables** — `AGENTBOARD_PORT`, `AGENTBOARD_HOST`, `AGENTBOARD_CONFIG`
3. **`agentboard.toml`** file — project root or path from `--config` / `AGENTBOARD_CONFIG`
4. **Built-in defaults** — see `config.py DEFAULTS` dict

### Config File Search Order

`config.py` looks for `agentboard.toml` in this order:
1. Path passed to `--config` CLI flag
2. Path in `AGENTBOARD_CONFIG` env var
3. `agentboard.toml` in project root (next to `server.py`)

If none found, defaults are used silently.

### `agentboard.toml` — All Options

```toml
[server]
host = "0.0.0.0"              # Bind address
port = 8765                    # Server port
cors_origins = ["*"]           # CORS allowed origins
proxy_prefix = ""              # Reverse proxy path prefix (e.g. "/board")
log_requests = false           # Enable HTTP request logging
maintenance = false            # Maintenance mode (all writes return 503)

[database]
path = "agentboard.db"         # SQLite file path (relative to project root)

[auth]
api_key_file = ".api_key"      # File to store/load API key
public_read = true             # Allow GET /api/* without auth

[features]
export_enabled = true           # Enable /api/export endpoints
import_enabled = true           # Enable /api/import endpoints
```

### CLI Flags

```bash
python server.py                    # Use defaults or agentboard.toml
python server.py --port 9000        # Override port
python server.py --host 127.0.0.1   # Override host
python server.py --log              # Enable request logging
python server.py --config /etc/ab.toml  # Use specific config file
python server.py -p 9000 -c prod.toml  # Short flags
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTBOARD_PORT` | Server port | `8765` |
| `AGENTBOARD_HOST` | Bind address | `0.0.0.0` |
| `AGENTBOARD_CONFIG` | Path to `agentboard.toml` | auto-detected |
| `AGENTBOARD_API_KEY` | API key (overrides `.api_key` file) | auto-generated |
| `AGENTBOARD_API_KEY_FILE` | API key file path | `.api_key` |
| `AGENTBOARD_DB_PATH` | Database file path | `agentboard.db` |
| `AGENTBOARD_PUBLIC_READ` | Allow GET without auth | `true` |
| `AGENTBOARD_MAINTENANCE` | Enable maintenance mode | `false` |
| `TZ` | Timezone for timestamps | `UTC` |

### Config Access in Code

```python
from config import get_config, reload_config

cfg = get_config()            # Lazy-loaded singleton
port = cfg["server"]["port"]  # 8765 (or overridden)

reload_config()               # Force re-read (useful in tests)
```

## Development

### ⚠️ Production Isolation Rule

**CRITICAL:** If a production server is running from this repository, NEVER `git checkout` a different branch without following this protocol:

```bash
# 1. Check if production is running — identify its CWD and branch
ps aux | grep "server.py" | grep -v grep

# 2. Stash any uncommitted changes
git stash

# 3. Ensure production stays on main (or its current branch)
git checkout main

# 4. Restart production from the correct branch
# (kill old process, restart from main)

# 5. NOW switch to your feature branch for development
git checkout -b feat/my-feature main
```

**Why:** `git checkout` changes the working tree files that the production server is using. If production is reading `server.py` and you switch branches, the running server may crash or serve wrong code.

**Safer alternative:** Clone to a separate directory for development:
```bash
git clone ~/agentboard /tmp/agentboard-dev
cd /tmp/agentboard-dev && git checkout -b feat/my-feature
```

### Dev Server

```bash
# Run dev server (auto-reload on file change)
python server.py --dev

# Run on different port (avoids conflicting with production)
AGENTBOARD_PORT=8766 python server.py
```

### Testing

```bash
# Run tests
python -m pytest tests/ -v

# Run single test file
python -m pytest tests/test_db.py -v
python -m pytest tests/test_auth.py -v
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
| `MAINTENANCE` | 503 | Server in maintenance mode (writes blocked) |
| `LAST_KEY` | 409 | Cannot delete the last active API key |

## Testing

```bash
# All tests use in-memory SQLite (:memory:)
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

## License

Apache 2.0 — see LICENSE file.
