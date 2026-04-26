# AgentBoard Agent Workflows

Step-by-step guides for common agent interaction patterns.

---

## Workflow 1: First-Time Setup

When an agent encounters AgentBoard for the first time:

```
1. Read .api_key file to get the API key
2. Verify connection: GET /api/stats
3. Register yourself: POST /api/agents
4. Check existing projects: GET /api/projects
5. If no projects exist: POST /api/setup (one-time)
```

**Key decisions:**
- If `/api/setup` returns `SETUP_DONE`, projects already exist — skip to step 4
- Always register your agent ID before creating tasks — it enables workload tracking

---

## Workflow 2: HITL (Human-In-The-Loop) Task Proposals

The core AgentBoard pattern — agents propose, humans approve.

```
1. Agent creates task with status="proposed"
   → Human sees it on dashboard under "Proposed" column

2. Human reviews and changes status:
   → "todo" = approved, not started
   → "in_progress" = approved and started
   → "review" = work done, needs review
   → Rejected = deleted by human

3. Agent polls for status changes:
   GET /api/tasks?project=all&assignee=my-agent-id
   → Filter for tasks where status != "proposed"

4. Agent starts work (status="in_progress"):
   PATCH /api/tasks/{id} {"status": "in_progress"}
   → Auto-sets started_at timestamp

5. Agent completes work (status="review"):
   PATCH /api/tasks/{id} {"status": "review", "description": "Done. Please review."}

6. Human approves:
   → Changes status to "done"
   → Agent sees completion on next poll
```

**Best practice:** Use `X-Actor` header so activity logs show which agent did what.

---

## Workflow 3: Multi-Step Task Execution

For complex tasks that need sub-steps:

```
1. Create parent task (e.g. "Build authentication system")
   POST /api/projects/{slug}/tasks {"status": "proposed", "priority": "high"}

2. Wait for human approval → status changes to "todo" or "in_progress"

3. Create sub-tasks as you progress:
   POST /api/projects/{slug}/tasks {"title": "Design DB schema", "status": "in_progress"}
   POST /api/projects/{slug}/tasks {"title": "Implement login API", "status": "proposed"}
   POST /api/projects/{slug}/tasks {"title": "Write tests", "status": "proposed"}

4. Update each sub-task as you complete them:
   PATCH /api/tasks/{id} {"status": "done"}

5. Update parent task when all sub-tasks done:
   PATCH /api/tasks/{parent_id} {"status": "review", "description": "All sub-tasks complete."}
```

---

## Workflow 4: Document Creation

Create project documentation (Outline-style nested pages):

```
1. Create root page:
   POST /api/projects/{slug}/pages {"title": "Project Plan", "content": "# Plan..."}

2. Create child pages:
   POST /api/projects/{slug}/pages {"title": "Requirements", "parent_id": "<root-id>"}
   POST /api/projects/{slug}/pages {"title": "Timeline", "parent_id": "<root-id>"}

3. Update content as project progresses:
   PATCH /api/pages/{id} {"content": "Updated requirements..."}

4. Reorganize if needed:
   POST /api/pages/{id}/move {"parent_id": "<new-parent>"}
```

---

## Workflow 5: Status Reporting

Generate a quick status report:

```
1. Get cross-project stats:
   GET /api/stats
   → Total tasks, completion %, per-project breakdown

2. Get agent workload:
   GET /api/agents/{id}/workload
   → Tasks by status, by project

3. Get recent activity:
   GET /api/activity?limit=20
   → What happened recently

4. Format report from the data above
```

---

## Workflow 6: Data Backup

Regular backup pattern:

```
1. Export all data:
   GET /api/export
   → Full JSON with all projects, tasks, pages, agents

2. Save to file:
   agentboard-backup-2026-04-26.json

3. Verify import works (optional):
   POST /api/import (on a fresh instance)
```

**Tip:** Use `?project={slug}` to export individual projects for selective backup.

---

## Workflow 7: Project Cleanup

Archive completed projects:

```
1. Check if project is done (all tasks done):
   GET /api/projects/{slug}
   → Check stats: total_tasks == done_tasks

2. Archive:
   DELETE /api/projects/{slug}
   → Soft delete — data preserved

3. Restore if needed:
   POST /api/projects/{slug}/restore
```

---

## Agent Best Practices

| Practice | Why |
|----------|-----|
| Always use `status="proposed"` for new tasks | Enables HITL approval workflow |
| Set `assignee` to your agent ID | Enables workload tracking and filtering |
| Use `X-Actor` header | Activity logs show who did what |
| Add comments when updating tasks | Provides context for humans reviewing later |
| Set `priority` on all tasks | Helps humans prioritize review queue |
| Use `due_date` for time-sensitive tasks | Visible on dashboard, helps with planning |
| Search before creating duplicate tasks | `GET /api/search?q=...` prevents redundancy |
| Keep descriptions concise but informative | Humans need context to make approval decisions |
| Update task description as you progress | Documents the work done, helps with handoffs |
