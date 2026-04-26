# AgentBoard

> Standalone multi-project task board for human+AI collaboration. Agent-native, zero dependencies.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

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

## Quick Start

### Option A: Standalone (no Docker)

```bash
git clone https://github.com/ajianaz/agentboard.git
cd agentboard
python server.py
```

Open **http://localhost:8765** — done. Database is auto-created.

First run prints your API key in the terminal and saves it to `.api_key`. Save it.

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
      - .:/opt/data/agentboard
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
Authorization: Bearer *** 
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

### Activity & Stats (2 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/activity` | Recent activity (all or by project) |
| GET | `/api/stats` | Cross-project summary |

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

**Total: 34 endpoints**

## Agent Integration

Any AI agent (Claude, GPT, local LLM, custom) can interact via REST API:

```bash
# Agent creates a task (proposed → needs human approval)
curl -X POST http://localhost:8765/api/projects/my-project/tasks \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Write launch email",
    "status": "proposed",
    "priority": "high",
    "assignee": "email-agent"
  }'

# Agent checks for feedback on HITL decisions
curl "http://localhost:8765/api/tasks?project=all&assignee=email-agent" \
  -H "Authorization: Bearer <api-key>"
```

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
│  Sidebar + Kanban + Docs + Stats    │
└──────────────┬──────────────────────┘
               │ fetch() → JSON API
               ▼
┌─────────────────────────────────────┐
│  server.py (Python stdlib)          │
│  Routing + Auth + API handlers      │
└──────────────┬──────────────────────┘
               │ SQLite
               ▼
┌─────────────────────────────────────┐
│  agentboard.db                      │
│  projects, tasks, pages, agents     │
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

## Quality Assurance

Standalone build tested for v1.0.0 release:

| Test Category | Result | Details |
|---------------|--------|---------|
| **API endpoints** | 13/13 ✅ | Root page, auth, CRUD project/task/page/comment, FTS search, stats, export, cascade delete |
| **HTML structure** | ✅ | DOCTYPE, charset+viewport, zero external deps, relative API paths, 49 JS functions, 15KB CSS dark theme |
| **Security** | ✅ | `_mask_key()` masks API key in banner, 500 returns generic error (no `str(exc)` leak), `.dockerignore` excludes secrets |
| **CI/CD** | 5/5 ✅ | pytest 3.11/3.12/3.13 + Docker amd64 + Docker arm64 |
| **Visual** | ⏭️ Skipped | No browser available in sandbox — requires testing on server with browser |

## Production Deployment

### Standalone (recommended for simplicity)

```bash
git clone https://github.com/ajianaz/agentboard.git /opt/data/agentboard
cd /opt/data/agentboard
cp .env.example .env  # optional — edit as needed
python3 server.py     # or use systemd/supervisor for process management
```

### Docker

```bash
git clone https://github.com/ajianaz/agentboard.git /opt/data/agentboard
cd /opt/data/agentboard
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
