---
name: agentboard
description: "Interact with AgentBoard project board via REST API — create projects, manage tasks, search, export. Works with any AI agent."
version: 1.0.0
tags: [project-management, task-board, api, agent-integration, hitl]
---

# AgentBoard — Agent API Skill

> Interact with any AgentBoard instance via REST API. Create projects, manage tasks, write docs, search, and collaborate with humans through the HITL workflow. Zero dependencies — works with `curl`, `python3`, or any HTTP client.

## When to Use

- "Create a project/task on AgentBoard"
- "Check my tasks" / "What's on the board?"
- "Search for tasks about X"
- "Export/backup AgentBoard data"
- "Update task status" / "Mark task as done"
- "Add a comment to a task"
- "Create a project document/page"

## Quick Reference

| Key | Value |
|-----|-------|
| **Default URL** | `http://localhost:8765` |
| **Auth** | `Authorization: Bearer <api_key>` |
| **Key file** | `.api_key` (auto-generated on first run) |
| **Content-Type** | `application/json` |
| **Response format** | `{"resource": {...}}` (wrapped) |
| **Total endpoints** | 31 |

## Key Rules

1. **Always auth** — All `/api/*` endpoints require `Authorization: Bearer <key>` (except `/api/setup`)
2. **Wrapped responses** — POST returns `{"project": {...}}`, `{"task": {...}}` — access via `d["project"]["slug"]`
3. **HITL pattern** — Agents create tasks as `proposed` → humans approve via dashboard
4. **Slug-based** — Projects identified by slug, tasks by ID
5. **Soft delete** — `DELETE /api/projects/{slug}` archives, doesn't destroy

## Setup (First Use)

```bash
# 1. Get API key (auto-generated on first run)
KEY=$(cat .api_key)

# 2. Verify connection
curl -s -H "Authorization: Bearer $KEY" http://localhost:8765/api/stats
```

## Common Workflow

```
Register agent → Create/find project → Create task (proposed) → Poll for human feedback → Update status
```

See [`references/workflows.md`](references/workflows.md) for detailed step-by-step guides.

## Linked Files

| File | Description |
|------|-------------|
| [`references/api_reference.md`](references/api_reference.md) | All 31 endpoints with request/response format |
| [`references/code_examples.md`](references/code_examples.md) | Python & curl code snippets for every operation |
| [`references/workflows.md`](references/workflows.md) | Common agent workflows (HITL, project setup, reporting) |
| [`references/pitfalls.md`](references/pitfalls.md) | Gotchas, edge cases, troubleshooting |
