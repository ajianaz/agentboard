# AgentBoard

> Standalone multi-project task board for human+AI collaboration. Agent-native, zero dependencies.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v1.5.3-green.svg)](https://github.com/ajianaz/agentboard/releases)

## What is it?

AgentBoard is a **project board that AI agents can actually use**. It's a single-file deployment (`python server.py`) with:

- 🗂️ **Multi-project kanban** — Marketing, Development, Finance, or any project you create
- 🤖 **Agent-native** — AI agents read `AGENTS.md` and immediately know the API
- ✅ **HITL (Human-In-The-Loop)** — Approve or reject agent proposals via dashboard
- 📝 **Outline-style docs** — Deeply nested document tree per project
- 📊 **Agent workload dashboard** — See who's working on what, across projects
- 🔍 **Full-text search** — FTS5-powered search across all tasks and pages
- 📦 **Export / Import** — Backup and restore projects as JSON
- 🌙 **Dark theme** — Built-in, no toggle needed
- 📦 **Zero dependencies** — Python 3.11+ stdlib only, no npm, no build step
- 📊 **Analytics dashboard** — Per-agent KPI cards with success rate, throughput, and activity metrics
- 💬 **Discussions** — Multi-round structured review system for proposals and decisions
- 📋 **Activity feed** — Filterable activity log with stats and trends

## Quick Start

### Option A: Standalone (no Docker)

```bash
git clone https://github.com/ajianaz/agentboard.git
cd agentboard
python server.py
```

Open **http://localhost:8765** — done. Database is auto-created.

First run prints your API key in the terminal and saves it to `.api_key`. Save it.

### First-Run Sample Data

```bash
python onboard.py --yes --sample-data
```

This registers demo agents, creates sample projects, tasks, a discussion with feedback, and pre-computed KPI metrics — so the analytics dashboard has data to show immediately.

**CLI flags** (optional):
```bash
python server.py --port 9000 --host 127.0.0.1 --log
python server.py --config /path/to/agentboard.toml
```

### Option B: Docker (from registry)

Pull pre-built image — no git clone needed:

```bash
mkdir -p agentboard && cd agentboard
curl -fsSL https://raw.githubusercontent.com/ajianaz/agentboard/main/.env.example -o .env
# Edit .env — set your API key
docker compose up -d
```

docker-compose.yml:
```yaml
services:
  agentboard:
    image: ghcr.io/ajianaz/agentboard:latest
    env_file: ./.env
    volumes:
      - .:/app
    ports:
      - "8765:8765"
```

Open **http://localhost:8765** — done.

**Available tags:**

| Tag | Description |
|-----|-------------|
| `latest` | Stable release (main branch) |
| `develop` | Bleeding edge (develop branch) |
| `v1.0.0` | Version pin |

### Option C: Docker (build from source)

```bash
git clone https://github.com/ajianaz/agentboard.git
cd agentboard
# Uncomment 'build: .' in docker-compose.yml, comment 'image: ...'
docker compose up -d
```

**Data persistence** — database and API key live in the bind-mounted directory (`./` by default). They survive container restarts and recreates.

**Adding to existing docker-compose** — copy the `agentboard` service from `docker-compose.yml` into your own compose file, adjust the network if needed.

## API Key

On first run, AgentBoard auto-generates a cryptographically random API key and:

1. **Prints it to the console** so you can copy it immediately
2. **Saves it to `.api_key`** in the project root for persistence

### Public Read-Only Mode

By default (`auth.public_read = true`), all **GET endpoints are accessible without authentication**. This means anyone can browse the board — view projects, tasks, agents, and search.

**Write operations** (POST, PATCH, DELETE) always require the API key:

```
Authorization: Bearer <api_key> 
```

To disable public read and require auth for **all** endpoints:

```bash
# Environment variable
AGENTBOARD_PUBLIC_READ=false

# Or in agentboard.toml
[auth]
public_read = false
```

You can override the API key with the `AGENTBOARD_API_KEY` environment variable, or set a custom key file path in `agentboard.toml`.

### Multi-Key Auth & Rotation (v1.2.0)

AgentBoard supports multiple API keys with rotation and grace periods:

- **Keys stored hashed** — raw key is shown only once on creation
- **Grace period** — deactivated keys work for N minutes before being fully rejected
- **Last key protection** — cannot delete the last active key
- **Legacy migration** — existing `.api_key` file is auto-imported on first v3 schema boot

Manage keys via the **⚙️ Settings** page in the UI, or the API:

```bash
# Create a new key
curl -X POST http://localhost:8765/api/auth/keys \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{"label": "ci-bot"}'
# → {"key": "ab_xxx...", "warning": "Save this key now"}

# Deactivate with 5-minute grace
curl -X PATCH http://localhost:8765/api/auth/keys/{id} \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{"deactivate": true, "grace_minutes": 5}'
```

### Maintenance Mode

Enable maintenance mode to block all write operations (reads continue normally):

```bash
# Enable via environment
AGENTBOARD_MAINTENANCE=true python server.py

# Or in agentboard.toml
[server]
maintenance = true
```

All POST/PATCH/DELETE requests return `503 MAINTENANCE` when enabled. Health check (`/api/health`) reflects the current status.

### Auth Summary

| Request Type | Auth Required | Behavior |
|-------------|--------------|----------|
| `GET /api/*` | ❌ No (when `public_read=true`) | Browse freely |
| `POST /api/*` | ✅ Yes | Create resources |
| `PATCH /api/*` | ✅ Yes | Update resources |
| `DELETE /api/*` | ✅ Yes | Delete resources |
| `POST /api/setup` | ❌ No | First-run setup (always public) |
| Static files + `/` | ❌ No | SPA served always |

## API Overview

All endpoints return JSON. Base URL: `http://localhost:8765/api`

### Projects (7 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List all active projects |
| GET | `/api/projects?include_archived=1` | List including archived |
| GET | `/api/projects/{slug}` | Get project detail + stats |
| POST | `/api/projects` | Create project |
| PATCH | `/api/projects/{slug}` | Update project |
| DELETE | `/api/projects/{slug}` | Archive project |
| POST | `/api/projects/{slug}/restore` | Unarchive project |

### Tasks (8 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{slug}/tasks` | Tasks in project |
| GET | `/api/projects/{slug}/tasks?status=review&assignee=cto` | Filter by status/assignee |
| POST | `/api/projects/{slug}/tasks` | Create task |
| GET | `/api/tasks/{id}` | Get single task |
| PATCH | `/api/tasks/{id}` | Update task |
| DELETE | `/api/tasks/{id}` | Delete task |
| GET | `/api/tasks?project=all&assignee=agent-id` | Cross-project task query |
| GET | `/api/tasks/{id}/children` | List subtasks |

### Pages (5 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{slug}/pages` | Page tree (nested) |
| POST | `/api/projects/{slug}/pages` | Create page |
| PATCH | `/api/pages/{id}` | Update page |
| DELETE | `/api/pages/{id}` | Delete page |
| POST | `/api/pages/{id}/move` | Move page (change parent/position) |

### Agents (4 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | List all agents |
| POST | `/api/agents` | Register agent |
| PATCH | `/api/agents/{id}` | Update agent |
| GET | `/api/agents/{id}/workload` | Agent's task stats |

### Comments (4 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks/{id}/comments` | Comments on a task |
| POST | `/api/tasks/{id}/comments` | Add comment to task |
| GET | `/api/pages/{id}/comments` | Comments on a page |
| POST | `/api/pages/{id}/comments` | Add comment to page |

### Activity & Stats (3 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/activity` | Recent activity (all or by project) |
| GET | `/api/stats` | Cross-project summary |
| GET | `/api/activity/stats?days=7` | Activity statistics by action type |

### Analytics & KPI (6 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analytics/kpi?days=7&period=daily` | KPI summary metrics |
| GET | `/api/analytics/kpi/{agent_id}?days=7` | KPI for specific agent |
| GET | `/api/analytics/agents?days=7` | Agent performance cards |
| GET | `/api/analytics/trends?metric=success_rate&days=30` | Trend data over time |
| GET | `/api/analytics/export?format=csv&days=7` | Export analytics (JSON/CSV) |
| POST | `/api/analytics/recompute` | Trigger immediate KPI recomputation |

### Discussions (7 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/discussions?limit=50` | List discussions |
| GET | `/api/discussions/{id}` | Get discussion with feedback |
| POST | `/api/discussions` | Create new discussion |
| PATCH | `/api/discussions/{id}` | Update discussion |
| DELETE | `/api/discussions/{id}` | Delete discussion |
| POST | `/api/discussions/{id}/feedback` | Add feedback to discussion |
| GET | `/api/discussions/{id}/summary` | Discussion summary |

### Search (1 endpoint)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/search?q={query}&project={slug}` | FTS5 search across tasks + pages |

### Export / Import (2 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/export` | Export all projects as JSON |
| GET | `/api/export?project={slug}` | Export single project |
| POST | `/api/import` | Import from JSON export |

### Setup (1 endpoint)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/setup` | Initial admin setup (first run only) |

**Note:** `/api/setup` is a one-time endpoint — it can only be called once after the database is created. To add additional projects afterward, use `POST /api/projects`.

### Webhooks (2 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/webhook/task-update` | Update existing task status (agent-driven) |
| POST | `/api/webhook/agent-event` | Auto-track agent sessions as tasks |

#### Auto-Tracking (`/api/webhook/agent-event`)

Framework-agnostic endpoint that any AI agent can POST to. Automatically creates and manages tasks based on agent lifecycle events.

```bash
# Agent starts a session → auto-create task
curl -X POST http://localhost:8765/api/webhook/agent-event \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "research-agent",
    "event_type": "session_start",
    "session_id": "unique-session-abc123",
    "message": "Research competitor pricing strategies"
  }'

# Agent finishes → auto-mark task as done
curl -X POST http://localhost:8765/api/webhook/agent-event \
  -H "Authorization: Bearer ***" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "research-agent",
    "event_type": "session_end",
    "session_id": "unique-session-abc123"
  }'
```

**Event types:** `session_start`, `session_end`, `task_start`, `task_end`

**Features:**
- 🔁 **Dedup** — same `session_id` updates existing task instead of creating duplicate
- 🚫 **Cron filter** — sessions starting with `cron_` are ignored
- ⏱️ **Rate limit** — 60 requests/minute per agent
- 🏷️ **Auto-tag** — tasks get `["auto-tracked"]` tag
- 📋 **Activity log** — every create/update/complete is logged

**Agent → project routing** (config `agentboard.toml`):
```toml
[agents]
research-agent = "research"
writer-agent = "content"
# Unmapped agents → default "Agent Tasks" project
```

**Compatible with:** CrewAI, LangGraph, AutoGen, Claude Code, Pi, Hermes, or any framework that can `POST` JSON.

### Public Stats (1 endpoint)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats/public` | Anonymized board statistics |

**Total: 55 endpoints** (including `/api/health`)

## Agent Integration

Any AI agent (Claude, GPT, local LLM, custom) can interact via REST API. This repo includes a **ready-to-use agent skill** in `skills/agentboard/` — just clone and read `SKILL.md` to get started.

```bash
# Agent creates a task (proposed → needs human approval)
curl -X POST http://localhost:8765/api/projects/my-project/tasks \
  -H "Authorization: Bearer ab_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Write launch email",
    "status": "proposed",
    "priority": "high",
    "assignee": "email-agent"
  }'

# Agent checks for feedback on HITL decisions
curl "http://localhost:8765/api/tasks?project=all&assignee=email-agent" \
  -H "Authorization: Bearer ab_YOUR_KEY"
```

**Read [`skills/agentboard/SKILL.md`](skills/agentboard/SKILL.md) for the complete agent integration guide** — includes all 31 endpoints, code examples, HITL workflows, and troubleshooting.

**Read [AGENTS.md](AGENTS.md) for the complete API reference and agent workflow guide.**

## Custom Workflows

Each project can have its own status workflow:

```json
// Marketing project
{
  "statuses": [
    {"key": "backlog", "label": "Backlog", "color": "#6b7280"},
    {"key": "draft", "label": "Draft", "color": "#f59e0b"},
    {"key": "review", "label": "Review", "color": "#8b5cf6"},
    {"key": "published", "label": "Published", "color": "#22c55e"}
  ]
}

// Development project
{
  "statuses": [
    {"key": "proposed", "label": "Proposed", "color": "#f59e0b"},
    {"key": "todo", "label": "To Do", "color": "#6b7280"},
    {"key": "in_progress", "label": "In Progress", "color": "#3b82f6"},
    {"key": "review", "label": "Review", "color": "#8b5cf6"},
    {"key": "done", "label": "Done", "color": "#22c55e"}
  ]
}
```

## Architecture

```
┌─────────────────────────────────────┐
│  Browser (index.html SPA)           │
│  Sidebar + Kanban + Docs + Analytics │
└──────────────┬──────────────────────┘
               │ fetch() → JSON API
               ▼
┌─────────────────────────────────────┐
│  server.py (Python stdlib)          │
│  Routing + Auth + API handlers      │
│  + HMAC webhook receiver            │
└──────────────┬──────────────────────┘
               │ SQLite
               ▼
┌─────────────────────────────────────┐
│  agentboard.db                      │
│  projects, tasks, pages, agents     │
│  activity, kpi_daily, kpi_weekly    │
│  discussions, discussion_feedback    │
│  webhook_events                     │
└─────────────────────────────────────┘
```

**Tech stack:**

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+ stdlib (`http.server`) |
| Database | SQLite 3.46+ (WAL, FTS5, JSON1) |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Auth | Bearer token (API key) |
| Dependencies | **None** — zero external packages |

## Configuration (Optional)

All defaults work without a config file. Create `agentboard.toml` to customize:

```toml
[server]
host = "0.0.0.0"
port = 8765
cors_origins = ["*"]
proxy_prefix = ""
log_requests = false

[database]
path = "agentboard.db"

[auth]
api_key_file = ".api_key"
public_read = true

[features]
export_enabled = true
import_enabled = true

[analytics]
interval_seconds = 300  # KPI computation interval
retention_daily_kpi = 90
retention_weekly_kpi = 365
retention_activity = 180
```

### Priority: CLI args > env vars > TOML file > defaults

### CLI Flags

```bash
python server.py --port 9000 --host 127.0.0.1 --log
python server.py --config /path/to/agentboard.toml
python server.py -p 9000 -c prod.toml
```

### Environment Variables

Environment variables override `agentboard.toml` values:

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTBOARD_PORT` | Server port | `8765` |
| `AGENTBOARD_HOST` | Bind address | `0.0.0.0` |
| `AGENTBOARD_CONFIG` | Path to `agentboard.toml` | auto-detected |
| `AGENTBOARD_API_KEY` | API key (overrides `.api_key` file) | auto-generated |
| `AGENTBOARD_API_KEY_FILE` | API key file path | `.api_key` |
| `AGENTBOARD_DB_PATH` | Database file path | `agentboard.db` |
| `AGENTBOARD_PUBLIC_READ` | Public read-only GET access | `true` |
| `AGENTBOARD_MAINTENANCE` | Enable maintenance mode | `false` |

### Config is optional

No `agentboard.toml`? No problem. AgentBoard uses built-in defaults and auto-creates everything you need. The config loader uses Python 3.11+ stdlib `tomllib` — still zero pip install.

## Dark Theme

AgentBoard ships with a built-in dark theme — no configuration needed. Open the app and it's dark by default.

## Development

```bash
# Run tests (pytest required — not included in standalone)
python -m pytest tests/ -v

# Run with custom port
AGENTBOARD_PORT=9000 python server.py
```

## Development (Side-by-Side with Production)

To develop alongside a running production instance:

```bash
git clone -b develop https://github.com/ajianaz/agentboard.git ~/agentboard-dev
cd ~/agentboard-dev
AGENTBOARD_PORT=8766 python3 server.py
```

Production and development are fully isolated — separate databases,
separate API keys, separate ports. See [CONTRIBUTING.md](CONTRIBUTING.md)
for full development setup.

## Quality Assurance

Standalone build tested for v1.0.0 release:

| Test Category | Result | Details |
|---------------|--------|---------|
| **API endpoints** | 126/126 ✅ | Full CRUD + analytics + discussions + auth + search + export/import |
| **HTML structure** | ✅ | DOCTYPE, charset+viewport, zero external deps, relative API paths, dark theme |
| **Security** | ✅ | `_mask_key()` masks API key in banner, 500 returns generic error (no `str(exc)` leak), `.dockerignore` excludes secrets |
| **CI/CD** | 5/5 ✅ | pytest 3.11/3.12/3.13 + Docker amd64 + Docker arm64 |
| **Visual** | ⏭️ Skipped | No browser available in sandbox — requires testing on server with browser |

## Production Deployment

### Standalone (recommended for simplicity)

```bash
git clone https://github.com/ajianaz/agentboard.git ~/agentboard
cd ~/agentboard
cp .env.example .env  # optional — edit as needed
python3 server.py     # or use systemd/supervisor for process management
```

### Docker

```bash
git clone https://github.com/ajianaz/agentboard.git ~/agentboard
cd ~/agentboard
cp .env.example .env
docker compose up -d
```

**Available image tags:** `latest` (stable/main), `develop` (bleeding edge), `v*` (semver)

### Reverse Proxy (Traefik)

Uncomment the Traefik labels in `docker-compose.yml` and set your domain:

```yaml
# In docker-compose.yml — uncomment these lines:
networks:
  - public-net
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.agentboard.rule=Host(`board.example.com`)"
  - "traefik.http.routers.agentboard.entrypoints=websecure"
  - "traefik.http.routers.agentboard.tls.certresolver=myresolver"
  - "traefik.http.services.agentboard.loadbalancer.server.port=8765"
```

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
