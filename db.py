"""AgentBoard — SQLite database schema, migrations, and connection management.

This module provides the database layer for AgentBoard using SQLite with WAL mode,
FTS5 full-text search, and a versioned migration system.

Usage:
    from db import get_db, gen_id, slugify
    conn = get_db()  # Auto-creates and migrates on first use
"""

import re
import secrets
import sqlite3
from pathlib import Path

# DB_PATH resolved by config module at runtime
from config import get_config

DB_PATH = None  # set on first get_db() call

SCHEMA_VERSION = 7

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
    visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public', 'hidden')),
    metadata TEXT DEFAULT '{}',
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_projects_position ON projects(position);
CREATE INDEX IF NOT EXISTS idx_projects_archived ON projects(is_archived);
CREATE INDEX IF NOT EXISTS idx_projects_visibility ON projects(visibility);

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

-- Pages (Outline-style documents, recursive CTE-compatible with parent_id self-reference)
-- project_id nullable for standalone pages (no project required)
CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES pages(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Untitled',
    content TEXT DEFAULT '',
    icon TEXT DEFAULT '📄',
    position REAL DEFAULT 0,
    depth INTEGER DEFAULT 0,
    is_expanded INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public', 'hidden')),
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pages_project ON pages(project_id);
CREATE INDEX IF NOT EXISTS idx_pages_parent ON pages(parent_id);
CREATE INDEX IF NOT EXISTS idx_pages_visibility ON pages(visibility);

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
CREATE INDEX IF NOT EXISTS idx_activity_actor ON activity(actor);
CREATE INDEX IF NOT EXISTS idx_activity_action ON activity(action);

-- FTS5 Search — content-synced virtual tables
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

# Schema v5 tables — also available as standalone SQL for tests
_SCHEMA_V5 = """
-- KPI Daily: per-agent, per-day metrics
CREATE TABLE IF NOT EXISTS kpi_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    date TEXT NOT NULL,
    tasks_created INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_moved_to_review INTEGER DEFAULT 0,
    comments_added INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    avg_completion_hours REAL DEFAULT 0.0,
    activity_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(agent_id, date)
);
CREATE INDEX IF NOT EXISTS idx_kpi_daily_agent ON kpi_daily(agent_id);
CREATE INDEX IF NOT EXISTS idx_kpi_daily_date ON kpi_daily(date);
CREATE INDEX IF NOT EXISTS idx_kpi_daily_agent_date ON kpi_daily(agent_id, date);

-- KPI Weekly: aggregated weekly metrics
CREATE TABLE IF NOT EXISTS kpi_weekly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    week_start TEXT NOT NULL,
    tasks_created INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    avg_completion_hours REAL DEFAULT 0.0,
    activity_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(agent_id, week_start)
);
CREATE INDEX IF NOT EXISTS idx_kpi_weekly_agent ON kpi_weekly(agent_id);
CREATE INDEX IF NOT EXISTS idx_kpi_weekly_week ON kpi_weekly(week_start);

-- Discussions: multi-round review system
CREATE TABLE IF NOT EXISTS discussions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    title TEXT NOT NULL,
    target_type TEXT DEFAULT '' CHECK(target_type IN ('task', 'page', 'project', '')),
    target_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed', 'consensus')),
    current_round INTEGER DEFAULT 1,
    max_rounds INTEGER DEFAULT 5,
    visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public', 'hidden')),
    created_by TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_discussions_target ON discussions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_discussions_status ON discussions(status);
CREATE INDEX IF NOT EXISTS idx_discussions_created ON discussions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_discussions_visibility ON discussions(visibility);

-- Discussion Feedback: per-round participant feedback
CREATE TABLE IF NOT EXISTS discussion_feedback (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    discussion_id TEXT NOT NULL REFERENCES discussions(id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    participant TEXT NOT NULL,
    role TEXT DEFAULT '',
    verdict TEXT DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    word_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_discussion ON discussion_feedback(discussion_id);
CREATE INDEX IF NOT EXISTS idx_feedback_round ON discussion_feedback(discussion_id, round);
CREATE INDEX IF NOT EXISTS idx_feedback_participant ON discussion_feedback(discussion_id, participant);
"""

FULL_SCHEMA_SQL = SCHEMA_SQL + _SCHEMA_V5


def get_db(db_path=None) -> sqlite3.Connection:
    """Get a connection to the database. Auto-creates and migrates on first use.

    Args:
        db_path: Optional path to the database file. Defaults to config setting.

    Returns:
        sqlite3.Connection with WAL mode, foreign keys, and Row factory enabled.
    """
    global DB_PATH
    if DB_PATH is None:
        DB_PATH = get_config()["database"]["path"]
    path = db_path or str(DB_PATH)
    # Ensure parent directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
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
    """Run migrations sequentially. Each migration is a SQL block.

    Migrations are keyed by target version number. Add new migrations
    by incrementing SCHEMA_VERSION and adding an entry here.

    Args:
        conn: Active database connection.
        from_ver: Current schema version in the database.
        to_ver: Target schema version to migrate to.
    """
    import logging
    log = logging.getLogger("db.migration")

    migrations = {
        2: """ALTER TABLE tasks ADD COLUMN parent_id TEXT REFERENCES tasks(id);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id);""",
        3: """CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    key_hash TEXT NOT NULL UNIQUE,
    label TEXT DEFAULT 'default',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_used_at TEXT,
    grace_until TEXT
);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);""",
        4: """-- Schema v4: agent identity and permissions on api_keys
ALTER TABLE api_keys ADD COLUMN agent TEXT DEFAULT '';
ALTER TABLE api_keys ADD COLUMN permissions TEXT DEFAULT 'read,write';
CREATE INDEX IF NOT EXISTS idx_api_keys_agent ON api_keys(agent);""",
        5: """-- Schema v5: analytics, KPI, discussions, and retention indexes

-- KPI Daily: per-agent, per-day metrics
CREATE TABLE IF NOT EXISTS kpi_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    date TEXT NOT NULL,
    tasks_created INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    tasks_moved_to_review INTEGER DEFAULT 0,
    comments_added INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    avg_completion_hours REAL DEFAULT 0.0,
    activity_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(agent_id, date)
);
CREATE INDEX IF NOT EXISTS idx_kpi_daily_agent ON kpi_daily(agent_id);
CREATE INDEX IF NOT EXISTS idx_kpi_daily_date ON kpi_daily(date);
CREATE INDEX IF NOT EXISTS idx_kpi_daily_agent_date ON kpi_daily(agent_id, date);

-- KPI Weekly: aggregated weekly metrics
CREATE TABLE IF NOT EXISTS kpi_weekly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    week_start TEXT NOT NULL,
    tasks_created INTEGER DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    avg_completion_hours REAL DEFAULT 0.0,
    activity_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(agent_id, week_start)
);
CREATE INDEX IF NOT EXISTS idx_kpi_weekly_agent ON kpi_weekly(agent_id);
CREATE INDEX IF NOT EXISTS idx_kpi_weekly_week ON kpi_weekly(week_start);

-- Discussions: multi-round review system
CREATE TABLE IF NOT EXISTS discussions (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    title TEXT NOT NULL,
    target_type TEXT DEFAULT '' CHECK(target_type IN ('task', 'page', 'project', '')),
    target_id TEXT DEFAULT '',
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'closed', 'consensus')),
    current_round INTEGER DEFAULT 1,
    max_rounds INTEGER DEFAULT 5,
    visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public', 'hidden')),
    created_by TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_discussions_target ON discussions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_discussions_status ON discussions(status);
CREATE INDEX IF NOT EXISTS idx_discussions_created ON discussions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_discussions_visibility ON discussions(visibility);

-- Discussion Feedback: per-round participant feedback
CREATE TABLE IF NOT EXISTS discussion_feedback (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    discussion_id TEXT NOT NULL REFERENCES discussions(id) ON DELETE CASCADE,
    round INTEGER NOT NULL,
    participant TEXT NOT NULL,
    role TEXT DEFAULT '',
    verdict TEXT DEFAULT '' CHECK(verdict IN ('approve', 'conditional', 'reject', '')),
    content TEXT NOT NULL DEFAULT '',
    word_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_discussion ON discussion_feedback(discussion_id);
CREATE INDEX IF NOT EXISTS idx_feedback_round ON discussion_feedback(discussion_id, round);
CREATE INDEX IF NOT EXISTS idx_feedback_participant ON discussion_feedback(discussion_id, participant);""",
        6: """-- Schema v6: enrich discussions with context, participants, leader
ALTER TABLE discussions ADD COLUMN context TEXT DEFAULT '';
ALTER TABLE discussions ADD COLUMN participants TEXT DEFAULT '';
ALTER TABLE discussions ADD COLUMN leader TEXT DEFAULT '';""",
        7: """-- Schema v7: visibility (public/hidden) for projects, pages, discussions
-- Standalone pages: project_id becomes nullable (requires table rebuild)
-- CRITICAL: Must drop FTS5 table + triggers BEFORE renaming pages table,
-- then recreate them AFTER. FTS5 content=pages creates a hard reference
-- that blocks DROP TABLE pages.

-- Step 1: Add visibility to projects and discussions
ALTER TABLE projects ADD COLUMN visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public', 'hidden'));
ALTER TABLE discussions ADD COLUMN visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public', 'hidden'));
CREATE INDEX IF NOT EXISTS idx_projects_visibility ON projects(visibility);
CREATE INDEX IF NOT EXISTS idx_discussions_visibility ON discussions(visibility);

-- Step 2: Drop FTS5 virtual table and triggers that reference pages
DROP TRIGGER IF EXISTS pages_ai;
DROP TRIGGER IF EXISTS pages_ad;
DROP TRIGGER IF EXISTS pages_au;
DROP TABLE IF EXISTS pages_fts;

-- Step 3: Rebuild pages table (nullable project_id + visibility column)
CREATE TABLE IF NOT EXISTS _pages_new (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES pages(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Untitled',
    content TEXT DEFAULT '',
    icon TEXT DEFAULT '📄',
    position REAL DEFAULT 0,
    depth INTEGER DEFAULT 0,
    is_expanded INTEGER DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public', 'hidden')),
    created_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO _pages_new SELECT *, 'public' FROM pages;
DROP TABLE pages;
ALTER TABLE _pages_new RENAME TO pages;
CREATE INDEX IF NOT EXISTS idx_pages_project ON pages(project_id);
CREATE INDEX IF NOT EXISTS idx_pages_parent ON pages(parent_id);
CREATE INDEX IF NOT EXISTS idx_pages_visibility ON pages(visibility);

-- Step 4: Recreate FTS5 virtual table and triggers
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    title, content,
    content=pages,
    content_rowid=rowid,
    tokenize='porter unicode61'
);
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
-- Rebuild FTS index from existing pages so pre-existing rows are searchable
INSERT INTO pages_fts(pages_fts) VALUES('rebuild');""",
    }
    for ver in range(from_ver + 1, to_ver + 1):
        sql = migrations.get(ver)
        if sql:
            try:
                conn.executescript(sql)
                log.info("Migration v%d applied successfully", ver)
            except Exception as e:
                err_msg = str(e).lower()
                is_alter = "alter table" in sql.lower()
                if is_alter and "duplicate column" in err_msg:
                    # ALTER TABLE ADD COLUMN on a column that already exists — safe to skip
                    log.info("Migration v%d: column already exists, skipping ALTER TABLE", ver)
                else:
                    log.error("Migration v%d FAILED: %s — database may be in inconsistent state", ver, e)
                    raise  # Crash on migration failure — better to fail fast than run with corrupt schema
        conn.execute("INSERT INTO _schema_version (version) VALUES (?)", (ver,))
    conn.commit()


def slugify(text: str) -> str:
    """Generate a URL-safe slug from text.

    Converts to lowercase, replaces non-alphanumeric characters with hyphens,
    strips leading/trailing hyphens, and truncates to 50 characters.

    Args:
        text: Input string to slugify.

    Returns:
        URL-safe slug string, or 'untitled' if result is empty.
    """
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug[:50] or 'untitled'


def gen_id() -> str:
    """Generate a 16-character lowercase hex ID.

    Uses cryptographically secure random bytes via secrets.token_hex(8).

    Returns:
        16-character lowercase hexadecimal string.
    """
    return secrets.token_hex(8)
