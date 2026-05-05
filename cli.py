#!/usr/bin/env python3
"""AgentBoard CLI — 'docker ps' for AI agents.

Zero-dependency CLI using only Python stdlib.
Tracks agent sessions, tasks, and project status.

Usage:
    python3 cli.py status              # All projects + task counts
    python3 cli.py tasks marketing     # Tasks in a project
    python3 cli.py health              # Server health check
    python3 cli.py agents              # Recent agent activity
    python3 cli.py plans               # List plans
    python3 cli.py task-create proj --title "Fix bug" --priority high
    python3 cli.py task-update ID --status done
    python3 cli.py discussions         # Recent discussions
    python3 cli.py --json status       # Raw JSON output (any list command)

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

BOARD_URL = os.environ.get("AGENTBOARD_URL", os.environ.get("BOARD_URL", "http://localhost:8765"))
BOARD_KEY = os.environ.get("AGENTBOARD_API_KEY", os.environ.get("BOARD_KEY", ""))


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


def _api_post(path: str, data: dict | None = None, method: str = "POST") -> dict:
    """POST/PATCH request to AgentBoard API. Returns parsed JSON or raises."""
    url = f"{BOARD_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if BOARD_KEY:
        headers["Authorization"] = f"Bearer {BOARD_KEY}"
    payload = json.dumps(data).encode() if data else b""
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        raise SystemExit(f"{RED}HTTP {e.code}{RST} {body}")


# ── Formatters ───────────────────────────────────────────────────────────────

def _maybe_json(args, endpoint: str | None):
    """If --json flag is set, fetch and print raw JSON. Returns True if handled."""
    if not args.json:
        return False
    data = _api(endpoint)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return True


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
        "in_progress": YLW, "executing": YLW,
        "review": MAG,
        "todo": DIM, "backlog": DIM, "proposed": DIM,
        "approved": CYN,
        "rejected": RED,
    }
    return m.get(status, WHT)


def _status_icon(status: str) -> str:
    m = {
        "done": "✓", "completed": "✓",
        "in_progress": "◎", "executing": "▶",
        "review": "◈",
        "todo": "○", "backlog": "○", "proposed": "◇",
        "approved": "✦",
        "rejected": "✗",
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

def cmd_status(args):
    """Show all projects with task counts — like docker ps."""
    if _maybe_json(args, "/api/projects"):
        return
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
    endpoint = f"/api/projects/{args.project}/tasks"
    if _maybe_json(args, endpoint):
        return
    data = _api(endpoint)
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


def cmd_health(args):
    """Check AgentBoard server health."""
    if _maybe_json(args, "/api/health"):
        return
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


def cmd_agents(args):
    """Show recent agent activity."""
    if _maybe_json(args, "/api/activity?limit=20"):
        return
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


# ── Plan Commands ────────────────────────────────────────────────────────────

def cmd_plans(args):
    """List plans (optionally filtered by project or status)."""
    params = []
    if args.project:
        params.append(f"project={args.project}")
    if args.status:
        params.append(f"status={args.status}")
    qs = f"?{'&'.join(params)}" if params else ""
    endpoint = f"/api/plans{qs}"
    if _maybe_json(args, endpoint):
        return
    data = _api(endpoint)
    plans = data if isinstance(data, list) else data.get("plans", [])

    if not plans:
        print(f"{DIM}No plans found.{RST}")
        return

    print(f"\n{CYN}{BOLD}{'ID':>10}  {'STATUS':<12} {'AGENT':<10} {'PROJECT':<20} {'STEPS':>5}  {'CREATED'}{RST}")
    print(f"{DIM}{'─' * 10}  {'─' * 12} {'─' * 10} {'─' * 20} {'─' * 5}  {'─' * 12}{RST}")

    for p in plans:
        pid = p.get("id", "?")[:8]
        status = p.get("status", "proposed")
        agent = p.get("assignee", p.get("created_by", ""))[:9]
        project = p.get("project", "")[:18]
        steps = len(p.get("steps", []))
        created = p.get("created_at", "")[:10]

        c = _status_color(status)
        icon = _status_icon(status)
        slabel = f"{icon} {status}"

        print(f"  {WHT}{pid:>9}  {c}{slabel:<12}{RST} {BLU}{agent:<10}{RST} {project:<20} {steps:>5}  {DIM}{created}{RST}")

    from collections import Counter
    sc = Counter(p.get("status", "proposed") for p in plans)
    summary = "  ".join(f"{_status_icon(s)} {_status_color(s)}{v} {s}{RST}" for s, v in sc.most_common())
    print(f"\n  {summary}  {DIM}({len(plans)} plans){RST}\n")


def cmd_plan_show(args):
    """Show plan details."""
    data = _api(f"/api/plans/{args.plan_id}")
    plan = data.get("plan", data)

    pid = plan.get("id", "?")
    status = plan.get("status", "?")
    agent = plan.get("assignee", plan.get("created_by", ""))
    project = plan.get("project", "")
    desc = plan.get("description", "")
    ctx = plan.get("context", "")
    created = plan.get("created_at", "")
    updated = plan.get("updated_at", "")
    steps = plan.get("steps", [])
    mission = plan.get("mission_id", "")
    meta = plan.get("metadata", {})

    c = _status_color(status)
    icon = _status_icon(status)

    print(f"\n{CYN}{BOLD}Plan {pid[:8]}{RST}  {c}{icon} {status}{RST}")
    print(f"{DIM}{'─' * 50}{RST}")
    print(f"  Agent:   {BLU}{agent}{RST}")
    print(f"  Project: {project}")
    if mission:
        print(f"  Mission: {mission}")
    print(f"  Created: {created}")
    if updated and updated != created:
        print(f"  Updated: {updated}")

    if desc:
        print(f"\n  {BOLD}Description:{RST}")
        for line in desc.split("\n"):
            print(f"    {line}")

    if ctx:
        print(f"\n  {BOLD}Context:{RST}")
        for line in ctx.split("\n"):
            print(f"    {line}")

    if steps:
        print(f"\n  {BOLD}Steps ({len(steps)}):{RST}")
        for i, s in enumerate(steps, 1):
            title = s.get("title", "?")
            desc_s = s.get("description", "")
            result = s.get("result", "")
            st = s.get("status", "")
            c_s = _status_color(st) if st else DIM
            icon_s = _status_icon(st) if st else "○"
            print(f"    {c_s}{icon_s}{RST} {i}. {title}")
            if desc_s:
                print(f"       {DIM}{desc_s}{RST}")
            if result:
                print(f"       {GRN}→ {result[:60]}{RST}")

    if meta:
        print(f"\n  {BOLD}Metadata:{RST}")
        for k, v in meta.items():
            print(f"    {DIM}{k}: {v}{RST}")

    print()


def cmd_plan_create(args):
    """Create a new plan."""
    import sys as _sys
    desc = args.description or input("Description: ").strip()
    if not desc:
        raise SystemExit(f"{RED}Description is required.{RST}")

    steps_input = args.steps
    if steps_input:
        steps = [{"title": s.strip()} for s in steps_input.split(",") if s.strip()]
    else:
        steps = []
        print("Enter steps (empty line to finish):")
        while True:
            try:
                title = input(f"  Step {len(steps) + 1}: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not title:
                break
            steps.append({"title": title})

    payload = {
        "agent": args.agent or "",
        "project_slug": args.project,
        "description": desc,
        "steps": steps if steps else [],
    }
    if args.context:
        payload["context"] = args.context
    if args.mission:
        payload["mission_id"] = args.mission

    data = _api_post(f"/api/projects/{args.project}/plans", payload)
    plan = data.get("plan", data)
    pid = plan.get("id", data.get("plan_id", "?"))
    status = plan.get("status", data.get("status", "proposed"))
    print(f"  {GRN}✓{RST} Plan {CYN}{pid[:8]}{RST} created — {_status_color(status)}{_status_icon(status)} {status}{RST}")
    print(f"  {DIM}Steps: {len(steps)}{RST}\n")


def cmd_plan_approve(args):
    """Approve a proposed plan."""
    data = _api_post(f"/api/plans/{args.plan_id}/approve")
    plan = data.get("plan", data)
    status = plan.get("status", "approved")
    print(f"  {GRN}✓{RST} Plan {CYN}{args.plan_id[:8]}{RST} — {_status_color(status)}{_status_icon(status)} {status}{RST}\n")


def cmd_plan_reject(args):
    """Reject a proposed plan."""
    _api_post(f"/api/plans/{args.plan_id}/reject")
    print(f"  {RED}✗{RST} Plan {CYN}{args.plan_id[:8]}{RST} — {_status_color('rejected')}{_status_icon('rejected')} rejected{RST}\n")


def cmd_plan_execute(args):
    """Execute an approved plan."""
    data = _api_post(f"/api/plans/{args.plan_id}/execute")
    plan = data.get("plan", data)
    status = plan.get("status", "executing")
    print(f"  {YLW}▶{RST} Plan {CYN}{args.plan_id[:8]}{RST} — {_status_color(status)}{_status_icon(status)} {status}{RST}\n")


# ── Task CRUD Commands ────────────────────────────────────────────────────

def cmd_task_create(args):
    """Create a new task in a project."""
    title = args.title or input("Title: ").strip()
    if not title:
        raise SystemExit(f"{RED}Title is required.{RST}")

    payload = {
        "title": title,
        "description": args.description or "",
        "status": args.status or "todo",
        "priority": args.priority or "none",
        "assignee": args.assignee or "",
        "type": args.type or "",
        "tags": [t.strip() for t in args.tags.split(",")] if args.tags else [],
        "git_branch": args.branch or "",
    }
    if args.parent:
        payload["parent_id"] = args.parent

    data = _api_post(f"/api/projects/{args.project}/tasks", payload)
    task = data.get("task", data)
    tid = task.get("id", data.get("id", "?"))
    status = task.get("status", payload["status"])
    print(f"  {GRN}✓{RST} Task {CYN}{tid}{RST} created — {_status_color(status)}{_status_icon(status)} {status}{RST}")
    if args.branch:
        print(f"  {DIM}Branch: {args.branch}{RST}")
    print()


def cmd_task_update(args):
    """Update a task (status, assignee, etc)."""
    payload = {}
    if args.status:
        payload["status"] = args.status
    if args.assignee is not None:
        payload["assignee"] = args.assignee
    if args.priority:
        payload["priority"] = args.priority
    if args.branch is not None:
        payload["git_branch"] = args.branch
    if args.title:
        payload["title"] = args.title
    if args.description is not None:
        payload["description"] = args.description

    if not payload:
        raise SystemExit(f"{RED}No fields to update. Use --status, --assignee, --priority, --branch, or --title.{RST}")

    _api_post(f"/api/tasks/{args.task_id}", payload, method="PATCH")
    print(f"  {GRN}✓{RST} Task {CYN}{args.task_id}{RST} updated\n")


def cmd_discussions(args):
    """List recent discussions."""
    params = []
    if args.project:
        params.append(f"project={args.project}")
    qs = f"?{'&'.join(params)}" if params else ""
    endpoint = f"/api/discussions{qs}"
    if _maybe_json(args, endpoint):
        return
    data = _api(endpoint)
    discussions = data if isinstance(data, list) else data.get("discussions", [])

    if not discussions:
        print(f"{DIM}No discussions found.{RST}\n")
        return

    print(f"\n{CYN}{BOLD}{'ID':>10}  {'STATUS':<12} {'TASK':<10} {'AGENT':<10} {'MESSAGES':>8}  {'CREATED'}{RST}")
    print(f"{DIM}{'─' * 10}  {'─' * 12} {'─' * 10} {'─' * 10} {'─' * 8}  {'─' * 12}{RST}")

    for d in discussions:
        did = d.get("id", "?")[:8]
        status = d.get("status", "open")
        task = d.get("task_id", "")[:8] or "—"
        agent = d.get("agent", d.get("created_by", ""))[:9]
        msgs = d.get("message_count", len(d.get("messages", [])))
        created = d.get("created_at", "")[:10]

        c = _status_color(status)
        icon = _status_icon(status)
        slabel = f"{icon} {status}"
        print(f"  {WHT}{did:>9}  {c}{slabel:<12}{RST} {task:<10} {BLU}{agent:<10}{RST} {msgs:>8}  {DIM}{created}{RST}")

    print(f"\n  {DIM}Showing {len(discussions)} discussions{RST}\n")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    global BOARD_URL, BOARD_KEY

    parser = argparse.ArgumentParser(
        prog="agentboard",
        description="AgentBoard CLI — task tracking for AI agents",
    )
    parser.add_argument("--url", default=BOARD_URL, help="AgentBoard URL")
    parser.add_argument("--key", default="", help="API key")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Show all projects with task counts")
    sub.add_parser("health", help="Check server health")

    p_tasks = sub.add_parser("tasks", help="List tasks in a project")
    p_tasks.add_argument("project", help="Project slug")

    sub.add_parser("agents", help="Recent agent activity")

    # ── Plan subcommands ──
    p_plans = sub.add_parser("plans", help="List plans")
    p_plans.add_argument("--project", help="Filter by project slug")
    p_plans.add_argument("--status", help="Filter by status (proposed/approved/executing/done/rejected)")

    p_plan_show = sub.add_parser("plan-show", help="Show plan details")
    p_plan_show.add_argument("plan_id", help="Plan ID")

    p_plan_create = sub.add_parser("plan-create", help="Create a new plan")
    p_plan_create.add_argument("project", help="Project slug")
    p_plan_create.add_argument("--agent", default="", help="Assignee agent name")
    p_plan_create.add_argument("-d", "--description", default="", help="Plan description")
    p_plan_create.add_argument("--context", default="", help="Additional context")
    p_plan_create.add_argument("--steps", default="", help="Comma-separated step titles")
    p_plan_create.add_argument("--mission", default="", help="Mission ID to link")

    p_plan_approve = sub.add_parser("plan-approve", help="Approve a proposed plan")
    p_plan_approve.add_argument("plan_id", help="Plan ID")

    p_plan_reject = sub.add_parser("plan-reject", help="Reject a proposed plan")
    p_plan_reject.add_argument("plan_id", help="Plan ID")
    p_plan_reject.add_argument("--reason", default="", help="Rejection reason")

    p_plan_execute = sub.add_parser("plan-execute", help="Execute an approved plan")
    p_plan_execute.add_argument("plan_id", help="Plan ID")

    # ── Task CRUD subcommands ──
    p_task_create = sub.add_parser("task-create", help="Create a new task")
    p_task_create.add_argument("project", help="Project slug")
    p_task_create.add_argument("--title", default="", help="Task title (or prompt)")
    p_task_create.add_argument("-d", "--description", default="", help="Task description")
    p_task_create.add_argument("--status", default="todo", help="Initial status (default: todo)")
    p_task_create.add_argument("--priority", default="none", help="Priority (critical/high/medium/low/none)")
    p_task_create.add_argument("--assignee", default="", help="Assignee agent name")
    p_task_create.add_argument("--type", default="", help="Task type (task/bug/feature/chore/mission/slice)")
    p_task_create.add_argument("--tags", default="", help="Comma-separated tags")
    p_task_create.add_argument("--branch", default="", help="Git branch name")
    p_task_create.add_argument("--parent", default="", help="Parent task ID (for subtasks)")

    p_task_update = sub.add_parser("task-update", help="Update a task")
    p_task_update.add_argument("task_id", help="Task ID")
    p_task_update.add_argument("--status", help="New status")
    p_task_update.add_argument("--assignee", default=None, help="New assignee (empty string to clear)")
    p_task_update.add_argument("--priority", help="New priority")
    p_task_update.add_argument("--branch", default=None, help="Git branch (empty string to clear)")
    p_task_update.add_argument("--title", help="New title")
    p_task_update.add_argument("--description", default=None, help="New description (empty string to clear)")

    # ── Discussion subcommand ──
    p_disc = sub.add_parser("discussions", help="List discussions")
    p_disc.add_argument("--project", default="", help="Filter by project slug")

    args = parser.parse_args()

    # Allow global --url/--key override
    BOARD_URL = args.url
    BOARD_KEY = args.key or BOARD_KEY

    cmds = {
        "status": cmd_status,
        "tasks": cmd_tasks,
        "health": cmd_health,
        "agents": cmd_agents,
        "plans": cmd_plans,
        "plan-show": cmd_plan_show,
        "plan-create": cmd_plan_create,
        "plan-approve": cmd_plan_approve,
        "plan-reject": cmd_plan_reject,
        "plan-execute": cmd_plan_execute,
        "task-create": cmd_task_create,
        "task-update": cmd_task_update,
        "discussions": cmd_discussions,
    }

    if not args.command:
        parser.print_help()
        return

    cmds[args.command](args)


if __name__ == "__main__":
    main()
