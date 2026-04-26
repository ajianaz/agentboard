"""AgentBoard Python client — zero-dep wrapper for agent use.

Agents import this module to interact with AgentBoard without raw curl.
Reads API key automatically from .api_key file.

Usage:
    from client import Board

    board = Board()  # auto-reads key, defaults to localhost:8765

    # Check my tasks
    tasks = board.my_tasks("cto")

    # Create a proposed task
    task = board.create_task("hermes-fleet", "Fix auth bug",
                             status="proposed", assignee="cto")

    # Update task status
    board.update_task(task["id"], status="in_progress")
"""

import json
import urllib.error
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:8765"
DEFAULT_KEY_FILE = "/opt/data/agentboard/.api_key"


class AgentBoardError(Exception):
    """Raised when an API call fails."""

    def __init__(self, message: str, status: int = 0, code: str = ""):
        self.message = message
        self.status = status
        self.code = code
        super().__init__(f"[{status}] {message}" if status else message)


class Board:
    """AgentBoard API client.

    Args:
        base_url: API base URL. Defaults to localhost:8765.
        api_key: API key. Defaults to reading from .api_key file.
        actor: Agent ID for X-Actor header. Defaults to "owner".
    """

    def __init__(self, base_url: str = DEFAULT_BASE,
                 api_key: str | None = None, actor: str = "owner"):
        self.base_url = base_url.rstrip("/")
        self.actor = actor
        if api_key:
            self._key = api_key
        else:
            try:
                with open(DEFAULT_KEY_FILE) as f:
                    self._key = f.read().strip()
            except FileNotFoundError:
                raise AgentBoardError(
                    f"API key file not found: {DEFAULT_KEY_FILE}. "
                    "Run 'python3 server.py' first to generate it."
                )

    # ── Internal ──────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body, ensure_ascii=False).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._key}")
        if body:
            req.add_header("Content-Type", "application/json")
        req.add_header("X-Actor", self.actor)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode()
                err = json.loads(body_text)
            except (json.JSONDecodeError, ValueError):
                err = {}
            raise AgentBoardError(
                err.get("error", body_text or str(e)),
                status=e.code,
                code=err.get("code", ""),
            )
        except urllib.error.URLError as e:
            raise AgentBoardError(f"Connection failed: {e.reason}")

    # ── Projects ──────────────────────────────────────────────────────────

    def list_projects(self, include_archived: bool = False) -> list[dict]:
        """List all projects."""
        path = "/api/projects"
        if include_archived:
            path += "?include_archived=1"
        return self._request("GET", path).get("projects", [])

    def get_project(self, slug: str) -> dict:
        """Get project by slug."""
        return self._request("GET", f"/api/projects/{slug}")["project"]

    def create_project(self, name: str, **kwargs) -> dict:
        """Create a new project. kwargs: icon, color, description, statuses."""
        body = {"name": name, **kwargs}
        return self._request("POST", "/api/projects", body)["project"]

    # ── Tasks ─────────────────────────────────────────────────────────────

    def list_tasks(self, project_slug: str, **filters) -> list[dict]:
        """List tasks in a project. Filters: status, assignee, priority, tag."""
        params = "&".join(f"{k}={v}" for k, v in filters.items() if v)
        path = f"/api/projects/{project_slug}/tasks"
        if params:
            path += f"?{params}"
        return self._request("GET", path).get("tasks", [])

    def all_tasks(self, **filters) -> list[dict]:
        """Cross-project task list. Filters: status, assignee, priority."""
        params = "&".join(f"{k}={v}" for k, v in filters.items() if v)
        path = "/api/tasks?project=all"
        if params:
            path += f"?{params}"
        return self._request("GET", path).get("tasks", [])

    def my_tasks(self, agent_id: str) -> list[dict]:
        """Get all tasks assigned to an agent across projects."""
        return self.all_tasks(assignee=agent_id)

    def get_task(self, task_id: str) -> dict:
        """Get single task with comments."""
        return self._request("GET", f"/api/tasks/{task_id}")["task"]

    def create_task(self, project_slug: str, title: str, **kwargs) -> dict:
        """Create a task. kwargs: description, status, priority, assignee,
        tags, due_date, parent_id, created_by."""
        body = {"title": title, **kwargs}
        return self._request("POST", f"/api/projects/{project_slug}/tasks", body)["task"]

    def update_task(self, task_id: str, **kwargs) -> dict:
        """Update a task. kwargs: title, description, status, priority,
        assignee, tags, due_date, position, metadata, comment."""
        return self._request("PATCH", f"/api/tasks/{task_id}", kwargs)["task"]

    def delete_task(self, task_id: str) -> dict:
        """Delete a task."""
        return self._request("DELETE", f"/api/tasks/{task_id}")

    def get_subtasks(self, parent_id: str) -> list[dict]:
        """Get child tasks of a parent task."""
        return self._request("GET", f"/api/tasks/{parent_id}/children").get("tasks", [])

    # ── HITL Shortcuts ────────────────────────────────────────────────────

    def propose(self, project_slug: str, title: str, assignee: str,
                **kwargs) -> dict:
        """Create a proposed task (needs owner approval)."""
        return self.create_task(
            project_slug, title,
            status="proposed", assignee=assignee, **kwargs,
        )

    def start(self, task_id: str, comment: str = "") -> dict:
        """Mark task as in_progress."""
        body = {"status": "in_progress"}
        if comment:
            body["comment"] = comment
        return self.update_task(task_id, **body)

    def submit_review(self, task_id: str, comment: str = "") -> dict:
        """Submit task for review."""
        body = {"status": "review"}
        if comment:
            body["comment"] = comment
        return self.update_task(task_id, **body)

    def approve(self, task_id: str, comment: str = "") -> dict:
        """Owner approves proposed/review task."""
        body = {"status": "todo" if self.get_task(task_id).get("status") == "proposed" else "done"}
        if comment:
            body["comment"] = comment
        return self.update_task(task_id, **body)

    def reject(self, task_id: str, comment: str = "") -> dict:
        """Owner rejects proposed/review task."""
        body = {"status": "rejected"}
        if comment:
            body["comment"] = comment
        return self.update_task(task_id, **body)

    # ── Agents ────────────────────────────────────────────────────────────

    def list_agents(self) -> list[dict]:
        """List all registered agents."""
        return self._request("GET", "/api/agents").get("agents", [])

    def get_agent(self, agent_id: str) -> dict:
        """Get single agent profile."""
        return self._request("GET", f"/api/agents/{agent_id}")["agent"]

    def get_workload(self, agent_id: str) -> dict:
        """Get agent's task statistics across all projects."""
        return self._request("GET", f"/api/agents/{agent_id}/workload")

    # ── Comments ──────────────────────────────────────────────────────────

    def add_comment(self, task_id: str, content: str) -> dict:
        """Add comment to a task."""
        return self.update_task(task_id, comment=content)

    # ── Activity ──────────────────────────────────────────────────────────

    def recent_activity(self, project_slug: str | None = None) -> list[dict]:
        """Get recent activity log."""
        path = "/api/activity"
        if project_slug:
            path += f"?project={project_slug}"
        return self._request("GET", path).get("activity", [])

    # ── Search ────────────────────────────────────────────────────────────

    def search(self, query: str, project_slug: str | None = None) -> dict:
        """Full-text search across tasks and pages."""
        path = f"/api/search?q={urllib.parse.quote(query)}"
        if project_slug:
            path += f"&project={project_slug}"
        return self._request("GET", path)

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Get cross-project summary statistics."""
        return self._request("GET", "/api/stats")

    # ── Export ────────────────────────────────────────────────────────────

    def export_all(self) -> dict:
        """Export entire database as JSON."""
        return self._request("GET", "/api/export")

    def export_project(self, project_slug: str) -> dict:
        """Export single project as JSON."""
        return self._request("GET", f"/api/export?project={project_slug}")


# ── Convenience: import urllib.parse for search ──────────────────────────
import urllib.parse
