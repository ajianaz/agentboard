"""AgentBoard API client — standalone, zero pip dependencies.

Usage:
    from tools.client import tasks, create_task, update_task, kpi, activity
    from tools.client import create_discussion, add_feedback, close_discussion

    result = tasks("my-project", status="todo")
    for t in result["tasks"]:                          # NOTE: dict, not list
        print(t["title"], t["status"])

    t = create_task("my-project", title="...", assignee="dev-1")
    task_id = t["task"]["id"]                          # NOTE: nested under "task"

    update_task(task_id, status="in_progress")
    kpi()                                              # Analytics
    activity(limit=10)                                 # Activity feed

    d = create_discussion(title="...", context="...", participants=["agent-alpha","agent-beta"])
    disc_id = d["id"]
    add_feedback(disc_id, participant="agent-beta", verdict="approve", content="...")
    close_discussion(disc_id)

All GET requests are public (no auth needed).
POST/PATCH/DELETE need AGENTBOARD_API_KEY env var.
"""

__all__ = [
    "projects", "project",
    "tasks", "get_task", "create_task", "update_task", "delete_task",
    "agents", "get_agent",
    "kpi", "agent_kpi", "trends", "recompute",
    "activity",
    "discussions", "get_discussion", "create_discussion", "add_feedback", "close_discussion",
    "search",
    "health",
    "pprint",
]

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("AGENTBOARD_URL", "http://localhost:8765")
API_KEY = os.environ.get("AGENTBOARD_API_KEY", "")

# Default key file: .api_key in repo root (parent of tools/ dir)
_DEFAULT_KEY_FILE = str(Path(__file__).parent.parent / ".api_key")


def _auth_headers():
    """Return auth headers for write operations."""
    if not API_KEY:
        # Try reading from file
        key_file = os.environ.get("AGENTBOARD_KEY_FILE") or _DEFAULT_KEY_FILE
        try:
            with open(key_file) as f:
                key = f.read().strip()
        except FileNotFoundError:
            key = ""
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _request(method, path, data=None):
    """Make API request. Returns dict or None."""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if method in ("POST", "PATCH", "DELETE"):
        for k, v in _auth_headers().items():
            req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read())
            return {"error": err_body, "status": e.code}
        except Exception:
            return {"error": str(e), "status": e.code}
    except Exception as e:
        return {"error": str(e), "status": 0}


# ── Projects ──────────────────────────────────────────────

def projects():
    """List all projects."""
    return _request("GET", "/api/projects")


def project(slug):
    """Get project by slug."""
    return _request("GET", f"/api/projects/{slug}")


# ── Tasks ─────────────────────────────────────────────────

def tasks(project_slug, status=None, assignee=None, limit=50):
    """Get tasks for a project. Optional filters: status, assignee."""
    params = []
    if status:
        params.append(f"status={status}")
    if assignee:
        params.append(f"assignee={assignee}")
    if limit:
        params.append(f"limit={limit}")
    qs = f"?{'&'.join(params)}" if params else ""
    return _request("GET", f"/api/projects/{project_slug}/tasks{qs}")


def get_task(task_id):
    """Get a single task by ID."""
    return _request("GET", f"/api/tasks/{task_id}")


def create_task(project_slug, title, status="todo", assignee=None, priority=None, tags=None, due_date=None):
    """Create a new task."""
    data = {"title": title, "status": status}
    if assignee:
        data["assignee"] = assignee
    if priority:
        data["priority"] = priority
    if tags:
        data["tags"] = tags
    if due_date:
        data["due_date"] = due_date
    return _request("POST", f"/api/projects/{project_slug}/tasks", data)


def update_task(task_id, **kwargs):
    """Update a task. Any field can be updated."""
    return _request("PATCH", f"/api/tasks/{task_id}", kwargs)


def delete_task(task_id):
    """Delete a task."""
    return _request("DELETE", f"/api/tasks/{task_id}")


# ── Agents ────────────────────────────────────────────────

def agents():
    """List all agents."""
    return _request("GET", "/api/agents")


def get_agent(agent_id):
    """Get agent by ID."""
    return _request("GET", f"/api/agents/{agent_id}")


# ── Analytics ─────────────────────────────────────────────

def kpi():
    """Get KPI summary for all agents."""
    return _request("GET", "/api/analytics/kpi")


def agent_kpi(agent_id):
    """Get KPI for a specific agent."""
    return _request("GET", f"/api/analytics/kpi/{agent_id}")


def trends(days=7):
    """Get trend data. Default 7 days."""
    return _request("GET", f"/api/analytics/trends?days={days}")


def recompute():
    """Trigger KPI recomputation."""
    return _request("POST", "/api/analytics/recompute")


# ── Activity ──────────────────────────────────────────────

def activity(limit=20, agent=None, project=None, action=None):
    """Get activity log. Optional filters."""
    params = [f"limit={limit}"]
    if agent:
        params.append(f"actor={agent}")
    if project:
        params.append(f"project_id={project}")
    if action:
        params.append(f"action={action}")
    return _request("GET", f"/api/activity?{'&'.join(params)}")


# ── Discussions ───────────────────────────────────────────

def discussions(project_slug=None):
    """List discussions. Optionally filter by project."""
    qs = f"?project_id={project_slug}" if project_slug else ""
    return _request("GET", f"/api/discussions{qs}")


def get_discussion(discussion_id):
    """Get a discussion with all feedback."""
    return _request("GET", f"/api/discussions/{discussion_id}")


def create_discussion(title, context, participants, project_slug=None, max_rounds=2):
    """Create a new discussion."""
    data = {
        "title": title,
        "context": context,
        "participants": participants,
        "max_rounds": max_rounds,
    }
    if project_slug:
        data["project_id"] = project_slug
    return _request("POST", "/api/discussions", data)


def add_feedback(discussion_id, participant, verdict, content):
    """Add feedback to a discussion."""
    return _request("POST", f"/api/discussions/{discussion_id}/feedback", {
        "participant": participant,
        "verdict": verdict,
        "content": content,
    })


def close_discussion(discussion_id):
    """Close a discussion and generate summary."""
    return _request("PATCH", f"/api/discussions/{discussion_id}", {"status": "closed"})


# ── Search ────────────────────────────────────────────────

def search(query, project_slug=None, limit=20):
    """Full-text search across tasks and pages."""
    qs = f"?q={urllib.parse.quote(query)}&limit={limit}"
    if project_slug:
        qs += f"&project={project_slug}"
    return _request("GET", f"/api/search{qs}")


# ── Health ────────────────────────────────────────────────

def health():
    """Check server health."""
    return _request("GET", "/api/health")


# ── Convenience: Quick print ──────────────────────────────

def pprint(data, indent=2):
    """Pretty print JSON data."""
    if isinstance(data, dict) and "error" in data:
        print(f"❌ Error {data.get('status', '?')}: {data['error']}")
    else:
        print(json.dumps(data, indent=indent, ensure_ascii=False))
