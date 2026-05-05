# Task Metadata Convention

AgentBoard uses a `metadata` JSON column on tasks (and other entities) for extensible, schema-free data. This document defines **recommended keys and conventions** to keep metadata consistent across agents.

## Design Principles

1. **Flat where possible** — avoid deep nesting; use dot-separated keys for namespacing
2. **Optional by default** — no metadata key is required; agents add what's relevant
3. **Self-documenting** — key names should be obvious; add notes here for ambiguous ones
4. **No schema enforcement** — metadata is freeform JSON; these are conventions, not constraints

---

## Reserved Namespaces

### `plan.*` — Task Planning & Estimation

Stores the agent's plan, approach, or implementation strategy. Set when an agent creates or updates a task with a plan.

```json
{
  "plan": {
    "approach": "Refactor validation module to use composable validators",
    "steps": [
      "Extract field-level validators into functions",
      "Create composite validator class",
      "Add unit tests for edge cases",
      "Update API error responses"
    ],
    "estimated_hours": 3,
    "estimated_complexity": "medium",
    "dependencies": ["task-id-1", "task-id-2"],
    "tools_needed": ["terminal", "file"],
    "updated_at": "2026-05-05T13:00:00+07:00"
  }
}
```

| Key | Type | Description |
|-----|------|-------------|
| `plan.approach` | string | One-paragraph description of the approach |
| `plan.steps` | string[] | Ordered list of implementation steps |
| `plan.estimated_hours` | number | Time estimate in hours (0.5 = 30 min) |
| `plan.estimated_complexity` | string | `low`, `medium`, `high`, `critical` |
| `plan.dependencies` | string[] | Task IDs this task depends on |
| `plan.tools_needed` | string[] | Hermes toolsets required (`terminal`, `file`, `web`, etc.) |
| `plan.updated_at` | string | ISO 8601 timestamp (WIB) of last plan update |

### `session.*` — Auto-Tracking

Set by the `webhook_task.py` agent-event handler when tracking agent activity.

```json
{
  "session_id": "abc123",
  "auto_tracked": true,
  "event_type": "session_start"
}
```

| Key | Type | Description |
|-----|------|-------------|
| `session_id` | string | Hermes session identifier |
| `auto_tracked` | boolean | `true` if created via agent-event webhook |
| `event_type` | string | `session_start`, `session_end`, `task_start`, `task_end` |

### `cron.*` — Cron Job Tracking

Set when a task is created or managed by a Hermes cron job.

```json
{
  "cron_id": "4281637f61df",
  "cron_name": "daily-blog-distribution",
  "cron_schedule": "0 9 * * *"
}
```

| Key | Type | Description |
|-----|------|-------------|
| `cron_id` | string | Hermes cron job ID |
| `cron_name` | string | Human-readable cron name |
| `cron_schedule` | string | Cron expression |

### `result.*` — Task Outcome

Set when a task is completed to record what was done.

```json
{
  "result": {
    "summary": "Fixed parse_mode bug in blog_distribute.py",
    "files_changed": ["blog_distribute.py"],
    "tests_passed": 4,
    "commit_sha": "e2da5bc",
    "completed_at": "2026-05-05T14:30:00+07:00"
  }
}
```

| Key | Type | Description |
|-----|------|-------------|
| `result.summary` | string | One-line description of what was accomplished |
| `result.files_changed` | string[] | Files modified during the task |
| `result.tests_passed` | number | Number of tests that passed |
| `result.commit_sha` | string | Git commit SHA |
| `result.completed_at` | string | ISO 8601 timestamp (WIB) |

### `external.*` — External References

Links to external systems (issues, PRs, tickets, etc.).

```json
{
  "external": {
    "github_issue": 42,
    "github_pr": 15,
    "linear_issue": "ENG-123",
    "url": "https://github.com/org/repo/issues/42"
  }
}
```

---

## Agent-Specific Keys

Agents can define their own keys outside the reserved namespaces. Recommended format: `{agent}_{purpose}`, e.g.:

- `kai_content_id` — Ghost post ID for Kai
- `cfo_invoice_url` — Mayar/Stripe invoice for CFO
- `zeko_audit_type` — Security audit category for Zeko

---

## Legacy Keys (no namespace)

These keys exist in the DB from before convention was established. They still work but new tasks should use the namespaced versions:

| Legacy Key | Migration Path |
|------------|---------------|
| `pending` | → `result.pending_action` |
| `channel` | → `external.channel` |
| `msg_id` | → `external.message_id` |
| `action` | → `result.action` |
| `issue` | → `result.issue` |
| `webhook_pipeline` | → `cron.pipeline` |
| `cron_pipeline` | → `cron.pipeline` |
| `changes` | → `result.changes` |
| `files_changed` | → `result.files_changed` |
| `line` | → `result.line_changed` |
| `tests_passed` | → `result.tests_passed` |

No migration needed — both old and new keys work. Agents should use new keys going forward.
