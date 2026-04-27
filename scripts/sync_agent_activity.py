#!/usr/bin/env python3
"""sync_agent_activity.py — Sync agent_activity from hermes_memory → AgentBoard.

Reads new entries from hermes_memory.agent_activity and inserts them into
AgentBoard's activity table, mapping agent names to project context.

Usage:
    python3 /opt/data/agentboard/scripts/sync_agent_activity.py [--dry-run]

Cron schedule: every 5 minutes
    */5 * * * * python3 /opt/data/agentboard/scripts/sync_agent_activity.py

State: stores last_sync timestamp in /opt/data/agentboard/.sync_state.json
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────
HERMES_DB = "/opt/data/hermes_memory.db"
AGENTBOARD_DB = "/opt/data/agentboard/agentboard.db"
SYNC_STATE_FILE = Path(__file__).parent.parent / ".sync_state.json"
WIB = timezone(timedelta(hours=7))


def load_sync_state() -> str:
    """Load last sync timestamp from state file."""
    if SYNC_STATE_FILE.exists():
        data = json.loads(SYNC_STATE_FILE.read_text())
        return data.get("last_sync", "1970-01-01T00:00:00+07:00")
    return "1970-01-01T00:00:00+07:00"


def save_sync_state(ts: str):
    """Save last sync timestamp."""
    SYNC_STATE_FILE.write_text(json.dumps({
        "last_sync": ts,
        "updated_at": datetime.now(WIB).isoformat(),
    }))


def sync(dry_run: bool = False):
    """Sync new activity entries from hermes_memory to AgentBoard."""
    last_sync = load_sync_state()

    # ── Read from hermes_memory ─────────────────────────────────────
    hermes_conn = sqlite3.connect(HERMES_DB, timeout=10)
    hermes_conn.row_factory = sqlite3.Row

    rows = hermes_conn.execute(
        """SELECT id, agent, action, target, details, status, created_at
           FROM agent_activity
           WHERE created_at > ?
           ORDER BY created_at ASC""",
        (last_sync,),
    ).fetchall()
    hermes_conn.close()

    if not rows:
        print(f"[{datetime.now(WIB).strftime('%H:%M:%S')}] No new entries since {last_sync}")
        return 0

    # ── Connect to AgentBoard ───────────────────────────────────────
    ab_conn = sqlite3.connect(AGENTBOARD_DB, timeout=10)
    ab_conn.row_factory = sqlite3.Row

    # Build agent → project mapping from existing tasks
    agent_projects = {}
    task_rows = ab_conn.execute(
        """SELECT DISTINCT t.assignee, p.id as project_id
           FROM tasks t
           JOIN projects p ON t.project_id = p.id
           WHERE t.assignee IS NOT NULL AND t.assignee != ''"""
    ).fetchall()
    for r in task_rows:
        agent_projects.setdefault(r["assignee"], r["project_id"])

    synced = 0
    errors = 0
    latest_ts = last_sync

    for row in rows:
        try:
            agent = row["agent"]
            action = row["action"]
            target = row["target"] or ""
            details = row["details"] or "{}"
            created_at = row["created_at"]

            # Generate a stable ID based on hermes activity ID (dedup)
            activity_id = f"hermes_{row['id']}"

            # Check if already synced (idempotent)
            existing = ab_conn.execute(
                "SELECT id FROM activity WHERE id = ?", (activity_id,)
            ).fetchone()
            if existing:
                continue

            # Map to project
            project_id = agent_projects.get(agent)

            # Clean up details — keep it concise
            try:
                detail_dict = json.loads(details)
                # Only keep safe fields
                safe_detail = {}
                for key in ("action", "target", "severity", "status"):
                    if key in detail_dict:
                        safe_detail[key] = detail_dict[key]
                details = json.dumps(safe_detail)
            except (json.JSONDecodeError, TypeError):
                details = "{}"

            # Determine target_type and target_id
            target_type = "agent"
            target_id = agent
            if action in ("system_audit", "code_review", "architecture_design"):
                target_type = "project"
            elif action in ("implementation", "deployment"):
                target_type = "task"

            if not dry_run:
                ab_conn.execute(
                    """INSERT INTO activity
                       (id, project_id, target_type, target_id, action, actor, detail, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (activity_id, project_id, target_type, target_id,
                     action, agent, details, created_at),
                )

            synced += 1
            if created_at > latest_ts:
                latest_ts = created_at

        except Exception as e:
            errors += 1
            print(f"  ERROR syncing {row['id']}: {e}", file=sys.stderr)

    if not dry_run and synced > 0:
        ab_conn.commit()

    ab_conn.close()

    # Save state
    if synced > 0:
        save_sync_state(latest_ts)

    print(f"[{datetime.now(WIB).strftime('%H:%M:%S')}] Synced {synced} entries, {errors} errors")
    if dry_run:
        print("  (DRY RUN — no changes written)")
    return synced


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    sync(dry_run=dry_run)
