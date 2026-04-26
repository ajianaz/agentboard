---
name: agentboard
category: devops
description: AgentBoard — standalone multi-project task board for agent fleet coordination. Zero deps, SQLite, vanilla JS SPA. API-first with HITL workflow.
---

# AgentBoard

> Standalone task board for Hermes fleet coordination. Clone → onboard → use.

## Quick Reference

| Item | Value |
|------|-------|
| **Repo** | `github.com/ajianaz/agentboard` |
| **Branch** | `main` (production) |
| **Install** | `git clone --branch main https://github.com/ajianaz/agentboard.git` |
| **Setup** | `python3 server.py` → auto-creates DB + `.api_key` |
| **Onboard** | `python3 onboard.py --yes` → registers agents + projects |
| **API Base** | `http://127.0.0.1:8765/api` |
| **Dashboard** | `http://127.0.0.1:8765` |
| **Auth** | `Authorization: Bearer <key from .api_key>` |
| **Tech** | Python 3.11+ stdlib, SQLite WAL, vanilla HTML/CSS/JS |

## Files

| File | Purpose |
|------|---------|
| `AGENTS.md` | **Single source of truth** — full API reference, schema, conventions |
| `onboard.py` | Fleet onboard script — registers agents, creates starter projects |
| `skills/agentboard/SKILL.md` | This file — quick reference hub |
| `skills/agentboard/references/api_reference.md` | All 31+ endpoints with examples |
| `skills/agentboard/references/client.py` | **Python client wrapper** — `from client import Board` |
| `skills/agentboard/references/workflows.md` | Common agent workflows (7 patterns) |
| `skills/agentboard/references/pitfalls.md` | Gotchas, edge cases, troubleshooting (14 items) |

## Python Client (Recommended)

```python
import sys
sys.path.insert(0, "/opt/data/agentboard/skills/agentboard/references")
from client import Board

board = Board(actor="cto")  # auto-reads .api_key

# Check my tasks
tasks = board.my_tasks("cto")

# Propose a task
task = board.propose("hermes-fleet", "Fix auth bug", assignee="cto")

# Start working
board.start(task["id"], comment="On it")

# Submit for review
board.submit_review(task["id"], comment="Ready for review")

# Check workload
stats = board.get_workload("cto")
print(f"Total: {stats['total']}, Done: {stats['completed']}")
```

## Agent Workflow (TL;DR)

```bash
# 1. Get API key
KEY=$(cat /opt/data/agentboard/.api_key)

# 2. Check your tasks
curl -H "Authorization: Bearer $KEY" \
  "http://127.0.0.1:8765/api/tasks?project=all&assignee=YOUR_ID"

# 3. Create proposed task (needs owner approval)
curl -X POST -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  "http://127.0.0.1:8765/api/projects/{slug}/tasks" \
  -d '{"title":"...","status":"proposed","assignee":"YOUR_ID","created_by":"agent:YOUR_ID"}'

# 4. Update progress
curl -X PATCH -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  "http://127.0.0.1:8765/api/tasks/{id}" -d '{"status":"in_progress"}'

# 5. Submit for review
curl -X PATCH -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  "http://127.0.0.1:8765/api/tasks/{id}" -d '{"status":"review","comment":"Ready"}'
```

## HITL Task Lifecycle

```
proposed → todo → in_progress → review → done
                                  ↓
                              rejected → in_progress
```

- **Agent** creates tasks as `proposed` → owner approves → `todo`
- **Agent** works → `in_progress` → submits → `review`
- **Owner** approves → `done` OR rejects → `rejected` (agent revises)

## Key Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/stats` | Board overview |
| GET | `/api/tasks?project=all&assignee=me` | My tasks |
| POST | `/api/projects/{slug}/tasks` | Create task (supports `parent_id`) |
| PATCH | `/api/tasks/{id}` | Update task |
| GET | `/api/tasks/{id}/children` | Subtasks of a parent |
| GET | `/api/agents/{id}` | Agent profile |
| GET | `/api/agents/{id}/workload` | Agent workload |
| GET | `/api/search?q=...` | Full-text search |
| GET | `/api/export` | Full backup |
