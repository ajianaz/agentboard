# AgentBoard

> Standalone multi-project task board for human+AI collaboration. Agent-native, zero dependencies.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

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
- 📦 **Zero dependencies** — Python 3.13+ stdlib only, no npm, no build step

## Quick Start

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

## API Key

On first run, AgentBoard auto-generates a cryptographically random API key and:

1. **Prints it to the console** so you can copy it immediately
2. **Saves it to `.api_key`** in the project root for persistence

All API requests require the key in the `Authorization` header:

```
Authorization: Bearer ***
```

You can override it with the `AGENTBOARD_API_KEY` environment variable, or set a custom key file path in `agentboard.toml`.

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

### Tasks (6 endpoints)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects/{slug}/tasks` | Tasks in project |
| GET | `/api/projects/{slug}/tasks?status=review&assignee=cto` | Filter by status/assignee |
| POST | `/api/projects/{slug}/tasks` | Create task |
| PATCH | `/api/tasks/{id}` | Update task |
| DELETE | `/api/tasks/{id}` | Delete task |
| GET | `/api/tasks/{id}` | Get single task |

### Cross-Project Tasks (1 endpoint)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks?project=all&assignee=agent-id` | Cross-project task query |

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
| POST | `/api/setup` | Initial admin setup (first run) |

**Total: 31 endpoints**

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
| Backend | Python 3.13+ stdlib (`http.server`) |
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
| `AGENTBOARD_DB_PATH` | Database file path | `agentboard.db` |

### Config is optional

No `agentboard.toml`? No problem. AgentBoard uses built-in defaults and auto-creates everything you need. The config loader uses Python 3.11+ stdlib `tomllib` — still zero pip install.

## Dark Theme

AgentBoard ships with a built-in dark theme — no configuration needed.

![AgentBoard dark theme screenshot](docs/screenshots/dark-theme.png)

## Development

```bash
# Run dev server (auto-reload on file change)
python server.py --dev

# Run tests
python -m pytest tests/ -v

# Run with custom port
AGENTBOARD_PORT=9000 python server.py
```

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
