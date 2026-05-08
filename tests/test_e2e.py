"""E2E Integration tests for AgentBoard API.

Spins up a real AgentBoard server subprocess with a temp database,
then exercises all critical CRUD flows via HTTP — exactly like a real client.

Each test class uses the same server session (session-scoped fixture).
Tests are isolated by using unique slugs/identifiers per test.

Covers:
  - Auth (public read, write protection)
  - Project, Task, Page, Plan, Discussion, Message, Comment CRUD
  - Search (FTS5), Stats, Activity, Export/Import
  - Edge cases: 404, 400, 409, delete cascades
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Server fixture — subprocess approach (avoids import caching issues)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def server():
    """Start AgentBoard as a subprocess with temp DB. Yields (base_url, api_key)."""

    tmpdir = tempfile.mkdtemp(prefix="ab_e2e_")
    db_path = os.path.join(tmpdir, "agentboard.db")
    api_key = "e2e_test_key_ab123xyz"

    # Find a free port dynamically to avoid conflicts with stale processes
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    # Start server
    env = os.environ.copy()
    env["AGENTBOARD_PORT"] = str(port)
    env["AGENTBOARD_HOST"] = "127.0.0.1"
    env["AGENTBOARD_DB_PATH"] = db_path
    env["AGENTBOARD_API_KEY"] = api_key
    env["AGENTBOARD_PUBLIC_READ"] = "true"

    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge for debugging
    )

    base_url = f"http://127.0.0.1:{port}"

    # Wait for server to be ready
    for i in range(40):
        # Also check if the child process has exited (bind failure)
        ret = proc.poll()
        if ret is not None:
            out = proc.stdout.read().decode()
            pytest.fail(f"Server process exited prematurely (code {ret}):\n{out[:1000]}")
        try:
            r = urllib.request.urlopen(f"{base_url}/api/health", timeout=2)
            if r.status == 200:
                break
        except (ConnectionRefusedError, urllib.error.URLError, OSError):
            time.sleep(0.15)
    else:
        proc.kill()
        out = proc.stdout.read().decode()
        pytest.fail(f"Server failed to start:\n{out[:1000]}")

    # Expose proc for debugging
    server._proc = proc

    yield base_url, api_key

    # Print server errors on cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    out = proc.stdout.read().decode()
    # Print last 30 lines of server output for debugging
    lines = out.strip().split('\n')
    error_lines = [l for l in lines if any(kw in l for kw in ['Error', 'Traceback', 'Operational'])]
    if error_lines:
        print(f"\n[server stderr — last {min(len(error_lines), 30)} error lines]")
        for e in error_lines[-30:]:
            print(f"  {e}")

    # Cleanup temp dir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api(method, url, body=None, api_key=None, query_params=None):
    """Make HTTP request. Returns (status, data)."""
    if query_params:
        from urllib.parse import urlencode
        url = f"{url}?{urlencode(query_params)}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


_counter = 0

def _uid():
    """Generate a unique test identifier (no hyphens — FTS5 treats bare numbers as column refs)."""
    global _counter
    _counter += 1
    return f"{os.getpid()}{_counter}"


def create_project(base, key, name="Test", slug=None):
    if slug is None:
        slug = name.lower().replace(" ", "-") + "-" + _uid()[:6]
    s, d = api("POST", f"{base}/api/projects", {"name": name, "slug": slug}, key)
    assert s == 201, f"create_project failed: {s} {d}"
    return d["project"]


# ===========================================================================
# Tests — Auth
# ===========================================================================

class TestAuthE2E:
    def test_public_read_works_without_key(self, server):
        base, _ = server
        s, d = api("GET", f"{base}/api/projects")
        assert s == 200

    def test_write_requires_key(self, server):
        base, _ = server
        s, _ = api("POST", f"{base}/api/projects", {"name": "X", "slug": f"x-{_uid()}"})
        assert s == 401

    def test_write_succeeds_with_key(self, server):
        base, key = server
        s, d = api("POST", f"{base}/api/projects", {"name": "OK", "slug": f"auth-ok-{_uid()}"}, key)
        assert s == 201

    def test_health_always_public(self, server):
        base, _ = server
        s, d = api("GET", f"{base}/api/health")
        assert s == 200
        assert d["status"] == "ok"


# ===========================================================================
# Tests — Projects CRUD
# ===========================================================================

class TestProjectsE2E:
    def test_list_projects(self, server):
        base, key = server
        create_project(base, key, "List Test")
        s, d = api("GET", f"{base}/api/projects")
        assert s == 200
        assert len(d["projects"]) >= 1

    def test_get_project_by_slug(self, server):
        base, key = server
        p = create_project(base, key, "Slug Test")
        s, d = api("GET", f"{base}/api/projects/{p['slug']}")
        assert s == 200
        assert d["project"]["slug"] == p["slug"]

    def test_update_project(self, server):
        base, key = server
        p = create_project(base, key, "Update Test")
        s, d = api("PATCH", f"{base}/api/projects/{p['slug']}", {"description": "updated"}, key)
        assert s == 200

    def test_delete_project_archives(self, server):
        base, key = server
        p = create_project(base, key, "Delete Test")
        s, d = api("DELETE", f"{base}/api/projects/{p['slug']}", api_key=key)
        assert s == 200

    def test_404_for_unknown_slug(self, server):
        base, _ = server
        s, _ = api("GET", f"{base}/api/projects/nonexistent-slug-xyz")
        assert s == 404


# ===========================================================================
# Tests — Tasks CRUD (full lifecycle)
# ===========================================================================

class TestTasksE2E:
    def _mk_task(self, base, key, slug, **kw):
        data = {"title": "E2E task", "status": "todo"}
        data.update(kw)
        s, d = api("POST", f"{base}/api/projects/{slug}/tasks", data, key)
        assert s == 201, f"create_task: {s} {d}"
        return d["task"]

    def test_full_lifecycle(self, server):
        """Create → Read → Update → Delete → Verify 404."""
        base, key = server
        p = create_project(base, key, "Task Lifecycle")
        task = self._mk_task(base, key, p["slug"], title="Lifecycle Test")
        tid = task["id"]
        assert tid

        # Read
        s, d = api("GET", f"{base}/api/tasks/{tid}")
        assert s == 200
        assert d["task"]["title"] == "Lifecycle Test"

        # Update
        s, d = api("PATCH", f"{base}/api/tasks/{tid}", {"status": "in_progress"}, key)
        assert s == 200
        assert d["task"]["status"] == "in_progress"

        # Delete
        s, d = api("DELETE", f"{base}/api/tasks/{tid}", api_key=key)
        assert s == 200
        assert d.get("deleted") is True

        # Verify gone
        s, _ = api("GET", f"{base}/api/tasks/{tid}")
        assert s == 404

    def test_list_and_filter(self, server):
        base, key = server
        p = create_project(base, key, "Task Filter")
        slug = p["slug"]
        self._mk_task(base, key, slug, title="Filter A", status="todo")
        self._mk_task(base, key, slug, title="Filter B", status="done")
        self._mk_task(base, key, slug, title="Filter C", status="review")

        s, d = api("GET", f"{base}/api/projects/{slug}/tasks")
        assert s == 200
        assert len(d.get("tasks", [])) >= 3

        s, d = api("GET", f"{base}/api/projects/{slug}/tasks", query_params={"status": "done"})
        assert s == 200
        assert all(t["status"] == "done" for t in d.get("tasks", []))

    def test_task_with_metadata(self, server):
        base, key = server
        p = create_project(base, key, "Task Meta")
        task = self._mk_task(base, key, p["slug"],
                             title="Meta Task", assignee="e2e-bot",
                             tags=["bug", "urgent"], priority="high")
        assert task["assignee"] == "e2e-bot"
        assert "bug" in task["tags"]
        assert task["priority"] == "high"

    def test_status_progression(self, server):
        """todo → in_progress → review → done."""
        base, key = server
        p = create_project(base, key, "Status Flow")
        task = self._mk_task(base, key, p["slug"], title="Status Test")
        for status in ["in_progress", "review", "done"]:
            s, d = api("PATCH", f"{base}/api/tasks/{task['id']}", {"status": status}, key)
            assert s == 200, f"status {status}: {s} {d}"


# ===========================================================================
# Tests — Pages CRUD
# ===========================================================================

class TestPagesE2E:
    def _mk_page(self, base, key, slug, **kw):
        data = {"title": "E2E Page", "content": "hello"}
        data.update(kw)
        s, d = api("POST", f"{base}/api/projects/{slug}/pages", data, key)
        assert s == 201, f"create_page: {s} {d}"
        return d["page"]

    def test_full_lifecycle(self, server):
        base, key = server
        p = create_project(base, key, "Page LC")
        page = self._mk_page(base, key, p["slug"], title="Page Test")
        pid = page["id"]

        s, d = api("PATCH", f"{base}/api/pages/{pid}", {"title": "Updated", "content": "new"}, key)
        assert s == 200
        assert d["page"]["title"] == "Updated"

        s, d = api("DELETE", f"{base}/api/pages/{pid}", api_key=key)
        assert s == 200

    def test_nested_pages(self, server):
        base, key = server
        p = create_project(base, key, "Nested")
        parent = self._mk_page(base, key, p["slug"], title="Parent")
        child = self._mk_page(base, key, p["slug"], title="Child", parent_id=parent["id"])
        assert child["parent_id"] == parent["id"]
        assert child["depth"] == 1


# ===========================================================================
# Tests — Plans CRUD
# ===========================================================================

class TestPlansE2E:
    def _mk_plan(self, base, key, slug):
        s, d = api("POST", f"{base}/api/projects/{slug}/plans",
                   {"title": "E2E Plan", "description": "test"}, key)
        assert s == 201, f"create_plan: {s} {d}"
        return d["plan"]

    def test_full_lifecycle(self, server):
        base, key = server
        p = create_project(base, key, "Plan LC")
        plan = self._mk_plan(base, key, p["slug"])
        pid = plan["id"]

        s, d = api("GET", f"{base}/api/plans/{pid}", api_key=key)
        assert s == 200

        s, d = api("PATCH", f"{base}/api/plans/{pid}", {"title": "Updated Plan"}, key)
        assert s == 200

        s, d = api("DELETE", f"{base}/api/plans/{pid}", api_key=key)
        assert s == 200

    def test_list_plans(self, server):
        base, key = server
        p = create_project(base, key, "Plan List")
        self._mk_plan(base, key, p["slug"])
        self._mk_plan(base, key, p["slug"])
        s, d = api("GET", f"{base}/api/projects/{p['slug']}/plans")
        assert s == 200
        assert len(d.get("plans", [])) >= 2


# ===========================================================================
# Tests — Discussions
# ===========================================================================

class TestDiscussionsE2E:
    def _mk_disc(self, base, key):
        s, d = api("POST", f"{base}/api/discussions",
                   {"title": "E2E Disc", "content": "test"}, key)
        assert s == 201, f"create_disc: {s} {d}"
        return d  # discussions return flat dict, not {"discussion": {...}}

    def test_full_lifecycle(self, server):
        base, key = server
        disc = self._mk_disc(base, key)
        did = disc["id"]

        s, d = api("GET", f"{base}/api/discussions/{did}", api_key=key)
        assert s == 200

        s, d = api("DELETE", f"{base}/api/discussions/{did}", api_key=key)
        assert s == 200

    def test_list_discussions(self, server):
        base, key = server
        self._mk_disc(base, key)
        s, d = api("GET", f"{base}/api/discussions", api_key=key)
        assert s == 200
        assert len(d.get("discussions", d.get("items", []))) >= 1


# ===========================================================================
# Tests — Messages
# ===========================================================================

class TestMessagesE2E:
    def test_create_and_list(self, server):
        base, key = server
        s, d = api("POST", f"{base}/api/messages",
                   {"from_agent": "e2e", "to_agent": "test", "content": "hello"}, key)
        assert s == 201
        assert d["message"]["id"]

        s, d = api("GET", f"{base}/api/messages", api_key=key)
        assert s == 200
        assert len(d.get("messages", [])) >= 1

    def test_delete_message(self, server):
        base, key = server
        s, d = api("POST", f"{base}/api/messages",
                   {"from_agent": "e2e", "to_agent": "test", "content": "del me"}, key)
        mid = d["message"]["id"]
        s, d = api("DELETE", f"{base}/api/messages/{mid}", api_key=key)
        assert s == 200


# ===========================================================================
# Tests — Comments
# ===========================================================================

class TestCommentsE2E:
    def test_add_and_list(self, server):
        base, key = server
        p = create_project(base, key, "Comments")
        s, td = api("POST", f"{base}/api/projects/{p['slug']}/tasks",
                    {"title": "Comment Target"}, key)
        assert s == 201
        tid = td["task"]["id"]

        api("POST", f"{base}/api/tasks/{tid}/comments", {"author": "bot1", "content": "first"}, key)
        api("POST", f"{base}/api/tasks/{tid}/comments", {"author": "bot2", "content": "second"}, key)

        s, d = api("GET", f"{base}/api/tasks/{tid}/comments")
        assert s == 200
        assert len(d.get("comments", [])) >= 2


# ===========================================================================
# Tests — Stats, Activity, Search
# ===========================================================================

class TestStatsE2E:
    def test_stats(self, server):
        base, _ = server
        s, d = api("GET", f"{base}/api/stats")
        assert s == 200
        assert "total_tasks" in d

    def test_public_stats(self, server):
        base, _ = server
        s, d = api("GET", f"{base}/api/stats/public")
        assert s == 200

    def test_activity(self, server):
        base, key = server
        s, d = api("GET", f"{base}/api/activity", api_key=key)
        assert s == 200

    def test_agents(self, server):
        base, key = server
        s, d = api("GET", f"{base}/api/agents", api_key=key)
        assert s == 200


class TestSearchE2E:
    def test_search_finds_created_task(self, server):
        base, key = server
        p = create_project(base, key, "Search")
        unique_term = f"ZyxSearchTerm{_uid()}"
        api("POST", f"{base}/api/projects/{p['slug']}/tasks",
            {"title": unique_term, "status": "todo"}, key)
        # Retry search with backoff — FTS5 trigger propagation may be async
        for attempt in range(5):
            time.sleep(0.2 * (attempt + 1))
            s, d = api("GET", f"{base}/api/search", api_key=key, query_params={"q": unique_term})
            if s == 200:
                break
        assert s == 200, f"search failed after retries: {s} {d}"
        results = d.get("results", d.get("tasks", []))
        assert len(results) >= 1


# ===========================================================================
# Tests — Export / Import
# ===========================================================================

class TestExportImportE2E:
    def test_export_roundtrip(self, server):
        base, key = server
        p = create_project(base, key, "Export")
        api("POST", f"{base}/api/projects/{p['slug']}/tasks",
            {"title": "Export Me", "status": "todo"}, key)

        s, export_data = api("GET", f"{base}/api/export", api_key=key)
        assert s == 200, f"export failed: {s} {export_data}"
        assert len(export_data["projects"]) >= 1

        s, d = api("POST", f"{base}/api/import", {"data": export_data}, key)
        assert s == 200
        assert "imported" in d


# ===========================================================================
# Tests — Edge Cases
# ===========================================================================

class TestEdgeCasesE2E:
    def test_404_missing_task(self, server):
        base, _ = server
        s, _ = api("GET", f"{base}/api/tasks/nonexistent-xyz-123")
        assert s == 404

    def test_404_missing_page(self, server):
        base, _ = server
        s, _ = api("GET", f"{base}/api/pages/nonexistent-xyz-123")
        assert s == 404

    def test_400_empty_title(self, server):
        base, key = server
        p = create_project(base, key, "Validation")
        s, _ = api("POST", f"{base}/api/projects/{p['slug']}/tasks",
                   {"title": ""}, key)
        assert s == 400

    def test_duplicate_slug_auto_suffix(self, server):
        """Server appends numeric suffix for duplicate slugs instead of rejecting."""
        base, key = server
        p1 = create_project(base, key, "Dup Slug", slug=f"dup-slug-test-{_uid()}")
        # Create another project with the same explicit slug
        p2_name = f"Dup Slug {p1['slug']}"  # slugify will produce same base
        s, d = api("POST", f"{base}/api/projects",
                   {"name": p2_name, "slug": p1["slug"]}, key)
        # Should succeed with auto-suffixed slug (e.g. dup-slug-test-xxx-2)
        assert s == 201, f"duplicate slug handling: {s} {d}"
        assert d["project"]["slug"] != p1["slug"]

    def test_cross_project_task_query(self, server):
        base, key = server
        p1 = create_project(base, key, "Cross P1")
        p2 = create_project(base, key, "Cross P2")
        api("POST", f"{base}/api/projects/{p1['slug']}/tasks",
            {"title": "Cross 1", "assignee": "e2e-bot"}, key)
        api("POST", f"{base}/api/projects/{p2['slug']}/tasks",
            {"title": "Cross 2", "assignee": "e2e-bot"}, key)

        s, d = api("GET", f"{base}/api/tasks", query_params={"project": "all", "assignee": "e2e-bot"})
        assert s == 200
        assert len(d.get("tasks", [])) >= 2
