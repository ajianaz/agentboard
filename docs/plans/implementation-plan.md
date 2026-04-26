# AgentBoard — Master Implementation Plan

> **Context Recovery:** If context is lost, read this file + AGENTS.md → you have everything.

**Goal:** Build a standalone, multi-project task board for human+AI collaboration.

**Architecture:** Python stdlib HTTP server → SQLite WAL → Vanilla HTML/CSS/JS SPA. Single file deployment (`server.py`), zero dependencies beyond Python 3.13+.

**Tech Stack:** Python 3.13 (stdlib only), SQLite 3.46+ (FTS5, JSON1), HTML/CSS/JS (no framework).

---

## Roadmap — 4 Phases

```
Phase 0: Foundation      Week 1     [████████████████████] 100% planned
Phase 1: API Layer       Week 1-2   [████████████████████] 100% planned
Phase 2: Frontend SPA    Week 2-3   [████████████████████] 100% planned
Phase 3: Polish & MCP    Week 3-4   [░░░░░░░░░░░░░░░░░░░░] 0% planned
```

### Phase 0: Foundation (server.py, db.py, auth.py)
**Deliverable:** Server starts, serves static files, DB auto-created, auth works.

### Phase 1: API Layer (all REST endpoints)
**Deliverable:** Full CRUD for projects, tasks, pages, agents, comments, activity, search.

### Phase 2: Frontend SPA (index.html)
**Deliverable:** Complete UI — overview, kanban, docs, settings, dark theme, responsive.

### Phase 3: Polish & MCP
**Deliverable:** MCP server wrapper, docs, examples, release.

---

## Phase 0: Foundation — Detailed Tasks

### Task 0.1: Create db.py — Schema & Migration

**Objective:** SQLite database initialization with full schema, WAL mode, and migration system.

**Files:**
- Create: `db.py`

**Implementation:**

```python
import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "agentboard.db"

SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    icon TEXT DEFAULT '📋',
    color TEXT DEFAULT '#3b82f6',
    position INTEGER DEFAULT 0,
    statuses TEXT DEFAULT '[{"key":"proposed","label":"Proposed","color":"#f59e0b"},{"key":"todo","label":"To Do","color":"#6b7280"},{"key":"in_progress","label":"In Progress","color":"#3b82f6"},{"key":"review","label":"Review","color":"#8b5cf6"},{"key":"done","label":"Done","color":"#22c55e"}]',
    priorities TEXT DEFAULT '[{"key":"critical","label":"Critical","color":"#ef4444"},{"key":"high","label":"High","color":"#f97316"},{"key":"medium","label":"Medium","color":"#eab308"},{"key":"low","label":"Low","color":"#22c55e"},{"key":"none","label":"None","color":"#6b7280"}]',
    tags TEXT DEFAULT '[]',
    is_archived INTEGER DEFAULT 0,
    metadata TEXT DEFAULT '{}',
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_projects_position ON projects(position);
CREATE INDEX IF NOT EXISTS idx_projects_archived ON projects(is_archived);

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo',
    priority TEXT DEFAULT 'none',
    assignee TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    position REAL DEFAULT 0,
    due_date TEXT,
    started_at TEXT,
    completed_at TEXT,
    metadata TEXT DEFAULT '{}',
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee);

-- Pages (Outline-style documents, 25+ depth support)
CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES pages(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Untitled',
    content TEXT DEFAULT '',
    icon TEXT DEFAULT '📄',
    position REAL DEFAULT 0,
    depth INTEGER DEFAULT 0,
    is_expanded INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pages_project ON pages(project_id);
CREATE INDEX IF NOT EXISTS idx_pages_parent ON pages(parent_id);

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT DEFAULT '',
    avatar TEXT DEFAULT '🤖',
    color TEXT DEFAULT '#3b82f6',
    is_active INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Comments
CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    target_type TEXT NOT NULL CHECK(target_type IN ('task', 'page')),
    target_id TEXT NOT NULL,
    author TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_comments_target ON comments(target_type, target_id);

-- Activity Log
CREATE TABLE IF NOT EXISTS activity (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT REFERENCES projects(id),
    target_type TEXT NOT NULL,
    target_id TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    detail TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_activity_project ON activity(project_id);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity(created_at DESC);

-- FTS5 Search
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    title, description,
    content=tasks,
    content_rowid=rowid,
    tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    title, content,
    content=pages,
    content_rowid=rowid,
    tokenize='porter unicode61'
);

-- FTS Triggers for tasks
CREATE TRIGGER IF NOT EXISTS tasks_ai AFTER INSERT ON tasks BEGIN
    INSERT INTO tasks_fts(rowid, title, description) VALUES (new.rowid, new.title, new.description);
END;
CREATE TRIGGER IF NOT EXISTS tasks_ad AFTER DELETE ON tasks BEGIN
    INSERT INTO tasks_fts(tasks_fts, rowid, title, description) VALUES('delete', old.rowid, old.title, old.description);
END;
CREATE TRIGGER IF NOT EXISTS tasks_au AFTER UPDATE ON tasks BEGIN
    INSERT INTO tasks_fts(tasks_fts, rowid, title, description) VALUES('delete', old.rowid, old.title, old.description);
    INSERT INTO tasks_fts(rowid, title, description) VALUES (new.rowid, new.title, new.description);
END;

-- FTS Triggers for pages
CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
    INSERT INTO pages_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
END;
CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, old.content);
END;
CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
    INSERT INTO pages_fts(pages_fts, rowid, title, content) VALUES('delete', old.rowid, old.title, old.content);
    INSERT INTO pages_fts(rowid, title, content) VALUES (new.rowid, new.title, new.content);
END;
"""


def get_db(db_path=None) -> sqlite3.Connection:
    """Get a connection to the database. Auto-creates and migrates on first use."""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection):
    """Create tables if they don't exist, run migrations if needed."""
    conn.executescript(SCHEMA_SQL)
    # Check current version
    row = conn.execute("SELECT MAX(version) as v FROM _schema_version").fetchone()
    current = row['v'] if row['v'] else 0
    if current < SCHEMA_VERSION:
        _run_migrations(conn, current, SCHEMA_VERSION)


def _run_migrations(conn: sqlite3.Connection, from_ver: int, to_ver: int):
    """Run migrations sequentially. Each migration is a SQL block."""
    migrations = {
        # Future migrations go here:
        # 2: "ALTER TABLE tasks ADD COLUMN estimated_hours REAL DEFAULT 0;"
    }
    for ver in range(from_ver + 1, to_ver + 1):
        sql = migrations.get(ver)
        if sql:
            conn.executescript(sql)
        conn.execute("INSERT INTO _schema_version (version) VALUES (?)", (ver,))
    conn.commit()


def slugify(text: str) -> str:
    """Generate URL-safe slug from text."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug[:50] or 'untitled'


def gen_id() -> str:
    """Generate 16-char lowercase hex ID."""
    import secrets
    return secrets.token_hex(8)
```

**Commit:** `feat(db): schema, migrations, and connection management`

---

### Task 0.2: Create auth.py — API Key Authentication

**Objective:** API key generation, validation, and middleware.

**Files:**
- Create: `auth.py`

**Implementation:**

```python
import hashlib
import secrets
import os
from pathlib import Path

API_KEY_FILE = Path(__file__).parent / ".api_key"
SESSION_COOKIE = "agentboard_session"


def generate_api_key() -> str:
    """Generate a new random API key."""
    return f"ab_{secrets.token_urlsafe(32)}"


def hash_key(key: str) -> str:
    """Hash API key for storage (never store raw key)."""
    return hashlib.sha256(key.encode()).hexdigest()


def get_or_create_api_key() -> str:
    """Load existing API key from file, or generate new one."""
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()
    key = generate_api_key()
    API_KEY_FILE.write_text(key)
    API_KEY_FILE.chmod(0o600)
    return key


def validate_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of key against stored hash."""
    import hmac
    return hmac.compare_digest(hash_key(raw_key), stored_hash)


def check_auth(headers: dict, stored_hash: str) -> bool:
    """Extract API key from request headers and validate."""
    if not stored_hash:
        return True  # No auth configured yet (first-run setup)
    auth_header = headers.get('authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return validate_key(token, stored_hash)
    return False


def get_actor_from_headers(headers: dict) -> str:
    """Determine who is making the request (owner or agent)."""
    auth = headers.get('x-actor', '')
    if auth:
        return auth
    return 'owner'
```

**Commit:** `feat(auth): API key generation and validation`

---

### Task 0.3: Create server.py — HTTP Server & Router

**Objective:** Python stdlib HTTP server with URL routing, JSON response helpers, static file serving.

**Files:**
- Create: `server.py`

**Key Implementation Points:**

```python
#!/usr/bin/env python3
"""AgentBoard — Standalone multi-project task board for human+AI collaboration."""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import importlib

# Local imports
from db import get_db
from auth import get_or_create_api_key, hash_key, check_auth

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_PORT = 8765


class RequestHandler(BaseHTTPRequestHandler):
    """Main request handler with URL routing."""

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PATCH(self):
        self._route("PATCH")

    def do_DELETE(self):
        self._route("DELETE")

    def do_OPTIONS(self):
        self._send_cors_headers()
        self.send_response(204)
        self.end_headers()

    def _route(self, method: str):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        query = parse_qs(parsed.query)

        # Auth check (skip for static files and setup)
        if not path.startswith('/static') and path != '/api/setup':
            api_key_hash = hash_key(get_or_create_api_key())
            if not check_auth(self.headers, api_key_hash):
                self._json_response({"error": "Unauthorized", "code": "UNAUTHORIZED"}, 401)
                return

        # Static files
        if path == '/' or path == '':
            self._serve_file(STATIC_DIR / "index.html", "text/html")
            return
        if path.startswith('/static/'):
            self._serve_file(STATIC_DIR / path[8:], self._guess_content_type(path))
            return

        # API routes
        self._handle_api(method, path, query)

    def _handle_api(self, method, path, query):
        """Route API requests to handler modules."""
        # Lazy-load API modules
        # Routes are matched in api/__init__.py router
        from api import router
        body = self._read_body()
        result = router.handle(method, path, query, body, self.headers)
        if result is None:
            self._json_response({"error": "Not found", "code": "NOT_FOUND"}, 404)
        else:
            status, data = result
            self._json_response(data, status)

    def _read_body(self) -> bytes:
        length = int(self.headers.get('content-length', 0))
        return self.rfile.read(length) if length > 0 else b''

    def _json_response(self, data, status=200):
        self.send_response(status)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _serve_file(self, filepath: Path, content_type: str):
        if not filepath.exists() or not filepath.is_relative_to(STATIC_DIR):
            self._json_response({"error": "Not found"}, 404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'public, max-age=3600')
        self.end_headers()
        self.wfile.write(filepath.read_bytes())

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Actor')

    def _guess_content_type(self, path: str) -> str:
        types = {
            '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
            '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon', '.json': 'application/json',
        }
        ext = Path(path).suffix.lower()
        return types.get(ext, 'application/octet-stream')

    def log_message(self, format, *args):
        """Custom logging: suppress default stderr output."""
        pass  # Or: sys.stderr.write(f"[AgentBoard] {args[0]} {args[1]} {args[2]}\n")


def main():
    port = int(os.environ.get('AGENTBOARD_PORT', DEFAULT_PORT))
    host = os.environ.get('AGENTBOARD_HOST', '0.0.0.0')

    # Ensure DB exists
    get_db()

    # Print startup info
    api_key = get_or_create_api_key()
    print(f"AgentBoard v0.1.0")
    print(f"  Database: {BASE_DIR / 'agentboard.db'}")
    print(f"  API Key:  {api_key}")
    print(f"  URL:      http://{host}:{port}")
    print(f"  Auth:     Bearer {api_key}")

    server = HTTPServer((host, port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == '__main__':
    main()
```

**Commit:** `feat(server): HTTP server with routing and static file serving`

---

### Task 0.4: Create api/__init__.py — Router

**Objective:** URL router that maps paths to handler functions.

**Files:**
- Create: `api/__init__.py`

```python
"""API Router — maps URL paths to handler functions."""

from urllib.parse import parse_qs


class Router:
    """Simple regex-free router. Routes are registered as (method, pattern) → handler."""

    def __init__(self):
        self.routes = []

    def add(self, method: str, pattern: str, handler):
        """Register a route. Use {param} for path parameters."""
        self.routes.append((method.upper(), pattern, handler))

    def get(self, pattern: str):
        """Decorator for GET routes."""
        def decorator(fn):
            self.add('GET', pattern, fn)
            return fn
        return decorator

    def post(self, pattern: str):
        def decorator(fn):
            self.add('POST', pattern, fn)
            return fn
        return decorator

    def patch(self, pattern: str):
        def decorator(fn):
            self.add('PATCH', pattern, fn)
            return fn
        return decorator

    def delete(self, pattern: str):
        def decorator(fn):
            self.add('DELETE', pattern, fn)
            return fn
        return decorator

    def handle(self, method: str, path: str, query: dict, body: bytes, headers: dict):
        """Match and execute a route. Returns (status, data) or None."""
        for route_method, pattern, handler in self.routes:
            if route_method != method.upper():
                continue
            params = self._match(pattern, path)
            if params is not None:
                try:
                    return handler(params, query, body, headers)
                except Exception as e:
                    return 500, {"error": str(e), "code": "INTERNAL_ERROR"}
        return None

    def _match(self, pattern: str, path: str) -> dict | None:
        """Match pattern against path. Returns dict of params or None."""
        pattern_parts = pattern.strip('/').split('/')
        path_parts = path.strip('/').split('/')

        if len(pattern_parts) != len(path_parts):
            return None

        params = {}
        for pp, pathp in zip(pattern_parts, path_parts):
            if pp.startswith('{') and pp.endswith('}'):
                params[pp[1:-1]] = pathp
            elif pp != pathp:
                return None
        return params


# Global router instance
router = Router()

# Import all route modules to register them
from api import projects, tasks, pages, agents, comments, activity, search
```

**Commit:** `feat(router): URL pattern matching and route registration`

---

### Task 0.5: Create tests/ — Test Infrastructure

**Objective:** pytest setup with in-memory SQLite for all tests.

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

```python
# tests/conftest.py
import pytest
import sqlite3
import tempfile
import os

# Ensure we can import from project root
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def db_conn():
    """Provide a fresh in-memory SQLite connection with full schema."""
    from db import SCHEMA_SQL
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def api_key():
    """Provide a test API key."""
    from auth import generate_api_key, hash_key
    key = "ab_test_key_for_unit_tests"
    return key, hash_key(key)


@pytest.fixture
def sample_project(db_conn):
    """Create a sample project for testing."""
    from db import gen_id
    project_id = gen_id()
    db_conn.execute(
        "INSERT INTO projects (id, name, slug) VALUES (?, ?, ?)",
        (project_id, "Test Project", "test-project")
    )
    db_conn.commit()
    return {"id": project_id, "name": "Test Project", "slug": "test-project"}
```

**Commit:** `test: pytest setup with in-memory SQLite fixtures`

---

## Phase 1: API Layer — Detailed Tasks

### Task 1.1: api/projects.py — Project CRUD

**Objective:** Full CRUD for projects with slug validation and stats.

**Endpoints:**
- `GET /api/projects` — list (with `?include_archived=1`)
- `GET /api/projects/{slug}` — detail + task stats
- `POST /api/projects` — create (slug auto-generated from name)
- `PATCH /api/projects/{slug}` — update
- `DELETE /api/projects/{slug}` — archive (soft delete)
- `POST /api/projects/{slug}/restore` — unarchive
- `GET /api/stats` — cross-project summary
- `POST /api/setup` — first-run setup (create API key, first project)

### Task 1.2: api/tasks.py — Task CRUD

**Objective:** Full CRUD for tasks with cross-project support.

**Endpoints:**
- `GET /api/projects/{slug}/tasks` — tasks in project (filter: status, assignee, priority, tag)
- `POST /api/projects/{slug}/tasks` — create task
- `PATCH /api/tasks/{id}` — update task (status transitions, comments)
- `DELETE /api/tasks/{id}` — delete task
- `GET /api/tasks?project=all` — cross-project tasks
- `GET /api/tasks?project=all&status=review` — cross-project filter

**HITL Logic:**
- When task transitions to `review` → log activity "submitted for review"
- When task transitions from `review` to `done` → log activity "approved"
- When task transitions from `review` to `in_progress` → log activity "changes requested"
- When task created with `status=proposed` → log activity "proposed (needs approval)"
- When task transitions from `proposed` to `todo` → log activity "approved"
- When task transitions to `rejected` → log activity "rejected"

### Task 1.3: api/pages.py — Document Tree CRUD

**Objective:** Outline-style document tree with unlimited nesting depth.

**Endpoints:**
- `GET /api/projects/{slug}/pages` — page tree (nested, sorted by position)
- `POST /api/projects/{slug}/pages` — create page (with optional parent_id)
- `PATCH /api/pages/{id}` — update page content/title/icon
- `DELETE /api/pages/{id}` — delete page (cascade children)
- `POST /api/pages/{id}/move` — move page (change parent, reorder)

**Tree Building:** Recursive CTE query to build nested tree from flat rows.

### Task 1.4: api/agents.py — Agent Management

**Objective:** Register/update agents and get workload stats.

**Endpoints:**
- `GET /api/agents` — list all agents
- `POST /api/agents` — register agent
- `PATCH /api/agents/{id}` — update agent
- `GET /api/agents/{id}/workload` — task counts by status for this agent

### Task 1.5: api/comments.py — Comments

**Objective:** Add/list comments on tasks and pages.

**Endpoints:**
- `GET /api/tasks/{id}/comments` — list comments for task
- `POST /api/tasks/{id}/comments` — add comment to task
- `GET /api/pages/{id}/comments` — list comments for page
- `POST /api/pages/{id}/comments` — add comment to page

### Task 1.6: api/activity.py — Activity Log

**Objective:** Query activity log with filtering.

**Endpoints:**
- `GET /api/activity` — recent activity (all, paginated)
- `GET /api/activity?project={slug}` — activity for project
- `GET /api/activity?actor={agent_id}` — activity by agent

### Task 1.7: api/search.py — FTS5 Search

**Objective:** Full-text search across tasks and pages.

**Endpoints:**
- `GET /api/search?q={query}` — search all tasks + pages
- `GET /api/search?q={query}&project={slug}` — search within project
- `GET /api/search?q={query}&type=task` — search tasks only
- `GET /api/search?q={query}&type=page` — search pages only

---

## Phase 2: Frontend SPA — Detailed Tasks

### Task 2.1: HTML Shell + Sidebar

**Objective:** Base HTML structure with sidebar navigation, view routing, dark theme.

**Key Components:**
- `<nav id="sidebar">` — project list, agents, settings links
- `<main id="app">` — content area that swaps between views
- View router in JS (hash-based: `#overview`, `#project/marketing/board`, `#settings`)
- Dark theme CSS variables

### Task 2.2: Overview Page

**Objective:** Portfolio cards, attention queue, agent workload.

**Components:**
- Portfolio cards (one per project: task count, done %, critical count, overdue)
- Attention queue (tasks with `status=proposed` or `status=review`)
- Agent workload bar chart

### Task 2.3: Kanban Board

**Objective:** Column-based task board with drag-and-drop.

**Components:**
- Columns generated from project's `statuses` JSON
- Task cards (title, assignee avatar, priority badge, due date)
- Drag-and-drop between columns (HTML5 DnD API)
- Task detail modal (edit title, description, assignee, priority, tags)
- Create task button/form
- Filter by assignee, priority, tag

### Task 2.4: Document Tree

**Objective:** Outline-style nested document editor.

**Components:**
- Recursive tree view (collapsible, 25+ depth)
- Page editor (title + markdown content)
- Create/move/delete pages
- JS-side markdown rendering (lightweight, no dependency)

### Task 2.5: Project Settings

**Objective:** CRUD for projects and customize workflow.

**Components:**
- Create/edit project form (name, icon, color, description)
- Custom statuses editor (add/remove/reorder)
- Custom priorities editor
- Custom tags editor
- Archive/unarchive

### Task 2.6: Agent Management

**Objective:** View agents and their workload.

**Components:**
- Agent list with avatar, role, active status
- Per-agent task breakdown
- Register new agent

---

## Phase 3: Polish & MCP (Future)

- MCP server wrapper (`agentboard-mcp`)
- Keyboard shortcuts
- Export/import (JSON)
- More chart types in stats view
- v1.0.0 release

---

## Branch Strategy

```
main     ─────●─────────────────────────────────  (production-ready)
develop  ─────●─────●─────●─────●─────●─────●──  (integration)
feat/x   ──────●─────●──                           (feature branch)
                \    merge PR
                 → develop
```

- `main` — tagged releases only, never push directly
- `develop` — integration branch, all PRs merge here
- `feat/*` — feature branches from develop
- `fix/*` — bugfix branches from develop
- PR required to merge into develop

## Commit Conventions

```
feat(scope): description     # New feature
fix(scope): description      # Bug fix
refactor(scope): description # Code change (no feature/fix)
test(scope): description     # Adding tests
docs(scope): description     # Documentation
chore(scope): description    # Maintenance
```

Examples:
- `feat(db): add FTS5 search tables and triggers`
- `fix(tasks): handle null assignee in filter query`
- `test(api): add project CRUD integration tests`

## Testing Strategy

- All tests use `:memory:` SQLite (no file I/O)
- `conftest.py` provides fresh DB + sample data fixtures
- Run: `python -m pytest tests/ -v`
- Target: 80%+ coverage on API layer
