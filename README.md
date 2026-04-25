# AgentBoard

> Standalone multi-project task board for human+AI collaboration. Agent-native, zero dependencies.

## What is it?

AgentBoard is a **project board that AI agents can actually use**. It's a single-file deployment (`python server.py`) with:

- 🗂️ **Multi-project kanban** — Marketing, Development, Finance, or any project you create
- 🤖 **Agent-native** — AI agents read `AGENTS.md` and immediately know the API
- ✅ **HITL (Human-In-The-Loop)** — Approve or reject agent proposals via dashboard
- 📝 **Outline-style docs** — 25+ depth nested documents per project
- 📊 **Agent workload dashboard** — See who's working on what, across projects
- 🔍 **Full-text search** — FTS5-powered search across all tasks and pages
- 🌙 **Dark theme** — Built-in, no toggle needed
- 📦 **Zero dependencies** — Python 3.13+ stdlib only, no npm, no build step

## Quick Start

```bash
git clone https://github.com/ajianaz/agentboard.git
cd agentboard
python server.py
```

Open **http://localhost:8765** — done. Database is auto-created.

First run prints your API key in the terminal. Save it.

## How it works

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

## Agent Integration

Any AI agent (Claude, GPT, local LLM, custom) can interact via REST API:

```bash
# Agent creates a task (proposed → needs human approval)
curl -X POST http://localhost:8765/api/projects/my-project/tasks \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Write launch email",
    "status": "proposed",
    "priority": "high",
    "assignee": "email-agent"
  }'

# Agent checks for feedback
curl http://localhost:8765/api/tasks?project=all&assignee=email-agent \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Read [AGENTS.md](AGENTS.md) for the complete API reference and agent workflow guide.**

## Custom Workflows

Each project can have its own status workflow:

```json
// Marketing project
{
  "statuses": ["Backlog", "Draft", "Review", "Scheduled", "Published"]
}

// Development project  
{
  "statuses": ["Proposed", "Todo", "In Progress", "Review", "Testing", "Done"]
}
```

## Configuration (Optional)

All defaults work without config. Create `config.yaml` to customize:

```yaml
server:
  host: "0.0.0.0"
  port: 8765

database:
  path: "agentboard.db"

auth:
  api_key: ""  # Auto-generated if empty
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.13+ stdlib (`http.server`) |
| Database | SQLite 3.46+ (WAL, FTS5, JSON1) |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Auth | Bearer token (API key) |

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run with custom port
AGENTBOARD_PORT=9000 python server.py
```

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
