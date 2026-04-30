#!/usr/bin/env python3
"""AgentBoard CLI — 'docker ps' for AI agents.

Zero-dependency CLI using only Python stdlib.
Tracks agent sessions, tasks, and project status.

Usage:
    python3 cli.py status              # All projects + task counts
    python3 cli.py tasks marketing     # Tasks in a project
    python3 cli.py health              # Server health check
    python3 cli.py agents              # Recent agent activity

Environment:
    AGENTBOARD_URL  — Board URL (default: http://localhost:8765)
    AGENTBOARD_API_KEY — API key (optional)
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

# ── ANSI Colors ──────────────────────────────────────────────────────────────

RST = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[31m"
GRN = "\033[32m"
YLW = "\033[33m"
BLU = "\033[34m"
CYN = "\033[36m"
MAG = "\033[35m"
WHT = "\033[37m"

# ── Config ───────────────────────────────────────────────────────────────────

BOARD_URL = os.environ.get("AGENTBOARD_URL", "http://localhost:8765")
BOARD_KEY = os.environ.get("AGENTBOARD_API_KEY", "")


def _api(path: str) -> dict:
    """GET request to AgentBoard API. Returns parsed JSON or raises."""
    url = f"{BOARD_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if BOARD_KEY:
        headers["Authorization"] = f"Bearer {BOARD_KEY}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        raise SystemExit(f"{RED}HTTP {e.code}{RST} {body}")
    except urllib.error.URLError:
        raise SystemExit(f"{RED}Cannot connect to {BOARD_URL}{RST}\n  Is the server running? (python3 server.py)")
    except TimeoutError:
        raise SystemExit(f"{RED}Timeout{RST} — server at {BOARD_URL} did not respond")


# ── Formatters ───────────────────────────────────────────────────────────────

def _ago(iso: str) -> str:
    """Human-readable relative time from ISO timestamp."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(dt.tzinfo) - dt if dt.tzinfo else datetime.now() - dt.replace(tzinfo=None)
        s = int(delta.total_seconds())
        if s < 60:
            return "just now"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h ago"
        return f"{s // 86400}d ago"
    except Exception:
        return iso[:10]


def _status_color(status: str) -> str:
    m = {
        "done": GRN, "completed": GRN,
        "in_progress": YLW, "review": MAG,
        "todo": DIM, "backlog": DIM, "proposed": DIM,
    }
    return m.get(status, WHT)


def _status_icon(status: str) -> str:
    m = {
        "done": "✓", "completed": "✓",
        "in_progress": "◎", "review": "◈",
        "todo": "○", "backlog": "○", "proposed": "◇",
    }
    return m.get(status, "?")


def _pad(s: str, width: int) -> str:
    """Pad/truncate string to fit column width (accounting for ANSI codes)."""
    visible = len(s.replace("\033", "").replace("[", "").replace("m", ""))
    # Strip ANSI for length calc
    import re
    clean = re.sub(r"\033\[[0-9;]*m", "", s)
    diff = len(s) - len(clean)
    if len(clean) >= width:
        return s[:width + diff] + RST
    return s + " " * (width - len(clean))


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_status(_args):
    """Show all projects with task counts — like docker ps."""
    data = _api("/api/projects")
    projects = data if isinstance(data, list) else data.get("projects", [])

    if not projects:
        print(f"{DIM}No projects found.{RST}")
        return

    # Header
    print(f"\n{CYN}{BOLD}{'PROJECT':<24} {'TODO':>5} {'WIP':>5} {'DONE':>5} {'TOTAL':>6}{RST}")
    print(f"{DIM}{'─' * 24} {'─' * 5} {'─' * 5} {'─' * 5} {'─' * 6}{RST}")

    total_all = {"todo": 0, "in_progress": 0, "done": 0}

    for p in projects:
        counts = p.get("task_counts", {})
        todo = counts.get("todo", 0) + counts.get("backlog", 0) + counts.get("proposed", 0)
        wip = counts.get("in_progress", 0) + counts.get("review", 0)
        done = counts.get("done", 0)
        total = todo + wip + done

        total_all["todo"] += todo
        total_all["in_progress"] += wip
        total_all["done"] += done

        icon = p.get("icon", "📋")
        name = p.get("name", p.get("slug", "?"))

        # Color the project name based on activity
        print(f"  {icon} {name:<22} {DIM}{todo:>5} {YLW}{wip:>5} {GRN}{done:>5} {WHT}{total:>6}{RST}")

    # Summary
    t = total_all
    total = t["todo"] + t["in_progress"] + t["done"]
    print(f"{DIM}{'─' * 24} {'─' * 5} {'─' * 5} {'─' * 5} {'─' * 6}{RST}")
    print(f"  {BOLD}{'TOTAL':<22} {DIM}{t['todo']:>5} {YLW}{t['in_progress']:>5} {GRN}{t['done']:>5} {WHT}{total:>6}{RST}")
    print(f"\n  {BOARD_URL}  {DIM}({total} tasks across {len(projects)} projects){RST}\n")


def cmd_tasks(args):
    """List tasks in a project."""
    slug = args.project
    data = _api(f"/api/projects/{slug}/tasks")
    tasks = data if isinstance(data, list) else data.get("tasks", [])

    if not tasks:
        print(f"{DIM}No tasks in '{slug}'.{RST}")
        return

    print(f"\n{CYN}{BOLD}{'ID':>5}  {'STATUS':<14} {'TITLE':<40} {'ASSIGNEE':<12} {'CREATED'}{RST}")
    print(f"{DIM}{'─' * 5}  {'─' * 14} {'─' * 40} {'─' * 12} {'─' * 12}{RST}")

    for t in tasks:
        tid = t.get("id", "?")
        status = t.get("status", "todo")
        title = t.get("title", "?")[:38]
        assignee = t.get("assignee", "")
        created = t.get("created_at", "")[:10]

        c = _status_color(status)
        icon = _status_icon(status)
        slabel = f"{icon} {status}"

        print(f"  {WHT}{tid:>4}  {c}{slabel:<14}{RST} {title:<40} {DIM}{assignee:<12} {created}{RST}")

    # Count by status
    from collections import Counter
    sc = Counter(t.get("status", "todo") for t in tasks)
    summary = "  ".join(f"{_status_icon(s)} {_status_color(s)}{v} {s}{RST}" for s, v in sc.most_common())
    print(f"\n  {summary}  {DIM}({len(tasks)} tasks){RST}\n")


def cmd_health(_args):
    """Check AgentBoard server health."""
    data = _api("/api/health")
    status = data.get("status", "unknown")
    version = data.get("version", "?")
    maintenance = data.get("maintenance", False)

    if status == "ok" and not maintenance:
        print(f"  {GRN}●{RST} AgentBoard {BOLD}v{version}{RST} — {GRN}healthy{RST}")
    elif maintenance:
        print(f"  {YLW}●{RST} AgentBoard {BOLD}v{version}{RST} — {YLW}maintenance mode{RST}")
    else:
        print(f"  {RED}●{RST} AgentBoard {BOLD}v{version}{RST} — {RED}{status}{RST}")

    print(f"  {DIM}{BOARD_URL}{RST}\n")


def cmd_agents(_args):
    """Show recent agent activity."""
    data = _api("/api/activity?limit=20")
    activities = data if isinstance(data, list) else data.get("activities", [])

    if not activities:
        print(f"{DIM}No recent activity.{RST}")
        return

    print(f"\n{CYN}{BOLD}{'AGENT':<12} {'ACTION':<18} {'TARGET':<20} {'WHEN'}{RST}")
    print(f"{DIM}{'─' * 12} {'─' * 18} {'─' * 20} {'─' * 12}{RST}")

    for a in activities:
        agent = a.get("agent", "?")
        action = a.get("action", "?")
        target = a.get("target", "")[:18]
        when = a.get("created_at", "")
        ago = _ago(when)

        # Color by action type
        if action in ("error", "fail", "crash"):
            ac = RED
        elif action in ("done", "complete", "success"):
            ac = GRN
        elif action in ("start", "spawn", "create"):
            ac = CYN
        else:
            ac = WHT

        print(f"  {BLU}{agent:<12}{RST} {ac}{action:<18}{RST} {target:<20} {DIM}{ago}{RST}")

    print(f"\n  {DIM}Showing {len(activities)} most recent{RST}\n")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    global BOARD_URL, BOARD_KEY

    parser = argparse.ArgumentParser(
        prog="agentboard",
        description="AgentBoard CLI — task tracking for AI agents",
    )
    parser.add_argument("--url", default=BOARD_URL, help="AgentBoard URL")
    parser.add_argument("--key", default="", help="API key")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show all projects with task counts")
    sub.add_parser("health", help="Check server health")

    p_tasks = sub.add_parser("tasks", help="List tasks in a project")
    p_tasks.add_argument("project", help="Project slug")

    sub.add_parser("agents", help="Recent agent activity")

    args = parser.parse_args()

    # Allow global --url/--key override
    BOARD_URL = args.url
    BOARD_KEY = args.key or BOARD_KEY

    cmds = {
        "status": cmd_status,
        "tasks": cmd_tasks,
        "health": cmd_health,
        "agents": cmd_agents,
    }

    if not args.command:
        parser.print_help()
        return

    cmds[args.command](args)


if __name__ == "__main__":
    main()
