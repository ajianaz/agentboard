#!/usr/bin/env python3
"""AgentBoard Onboard — registers default agent fleet and creates starter projects.

Usage:
    python onboard.py                    # Interactive (asks for confirmation)
    python onboard.py --yes              # Non-interactive (auto-confirm)
    python onboard.py --agents-only      # Only register agents
    python onboard.py --projects-only    # Only create projects
    python onboard.py --sample-data      # Also create sample tasks, discussions, and activity

Run after `git clone` and `python server.py` (first run auto-generates .api_key).
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ── Config ──────────────────────────────────────────────────

BASE_URL = os.environ.get("AGENTBOARD_URL", "http://127.0.0.1:8765")
API_KEY_FILE = os.environ.get("AGENTBOARD_API_KEY_FILE", ".api_key")

DEFAULT_AGENTS = [
    {
        "id": "alpha",
        "name": "Alpha",
        "role": "Lead — Architecture, Planning, Coordination",
        "avatar": "🏗️",
        "color": "#3b82f6",
    },
    {
        "id": "beta",
        "name": "Beta",
        "role": "Engineer — Development, Security, Operations",
        "avatar": "🛡️",
        "color": "#ef4444",
    },
    {
        "id": "gamma",
        "name": "Gamma",
        "role": "Analyst — Research, Finance, Data",
        "avatar": "💰",
        "color": "#22c55e",
    },
]

DEFAULT_PROJECTS = [
    {
        "name": "My Project",
        "icon": "📋",
        "color": "#3b82f6",
        "description": "General coordination, infrastructure, and cross-team tasks",
    },
    {
        "name": "SaaS Core Engine",
        "icon": "⚙️",
        "color": "#f97316",
        "description": "Core product engine — backend, CLI, web templates",
    },
]

# ── API Helper ──────────────────────────────────────────────


def _load_api_key() -> str:
    """Load API key from file or env var."""
    key = os.environ.get("AGENTBOARD_API_KEY", "")
    if key:
        return key
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE) as f:
            return f.read().strip()
    return ""


def api(method: str, path: str, data: dict = None, actor: str = None) -> tuple:
    """Make API call. Returns (status_code, response_dict_or_str)."""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    key = _load_api_key()
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    if actor:
        req.add_header("X-Actor", actor)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        b = e.read().decode()
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, b
    except Exception as e:
        return None, str(e)


# ── Health Check ────────────────────────────────────────────


def check_server() -> bool:
    """Verify AgentBoard server is running."""
    code, _ = api("GET", "/api/stats")
    if code == 200:
        return True
    print(f"❌ Server not reachable at {BASE_URL}")
    print("   Make sure to run: python server.py")
    return False


# ── Register Agents ─────────────────────────────────────────


def register_agents(agents=None):
    """Register agent fleet. Skips existing agents (409)."""
    agents = agents or DEFAULT_AGENTS
    registered = 0
    skipped = 0
    errors = 0

    print(f"\n📋 Registering {len(agents)} agents...")
    for agent in agents:
        code, resp = api("POST", "/api/agents", agent)
        if code in (200, 201):
            registered += 1
            print(f"  ✅ {agent['id']:12s}  {agent['avatar']} {agent['name']}")
        elif code == 409:
            skipped += 1
            print(f"  ⏭️  {agent['id']:12s}  already exists")
        else:
            errors += 1
            err = resp.get("error", resp) if isinstance(resp, dict) else resp
            print(f"  ❌ {agent['id']:12s}  {err}")

    print(f"\n  Result: {registered} registered, {skipped} skipped, {errors} errors")
    return registered


# ── Create Projects ─────────────────────────────────────────


def _slugify(name: str) -> str:
    """Simple slug generation matching AgentBoard's server logic."""
    slug = name.lower().strip()
    for ch in " !@#$%^&*()+={}[]|\\:;\"'<>,?/":
        slug = slug.replace(ch, "-")
    slug = "-".join(s for s in slug.split("-") if s)
    return slug[:60]


def create_projects(projects=None):
    """Create starter projects. Checks existing projects first — fully idempotent."""
    projects = projects or DEFAULT_PROJECTS

    # Fetch existing project slugs
    code, resp = api("GET", "/api/projects")
    existing_slugs = set()
    if code == 200:
        existing_slugs = {p["slug"] for p in resp.get("projects", [])}

    created = 0
    skipped = 0
    errors = 0

    print(f"\n📂 Creating {len(projects)} projects...")
    for proj in projects:
        expected_slug = _slugify(proj["name"])
        if expected_slug in existing_slugs:
            skipped += 1
            print(f"  ⏭️  {proj['name']:25s}  already exists (slug: {expected_slug})")
            continue

        code, resp = api("POST", "/api/projects", proj)
        if code in (200, 201):
            created += 1
            p = resp.get("project", resp)
            print(f"  ✅ {p.get('slug', '?'):25s}  {proj['icon']} {proj['name']}")
        elif code == 409:
            skipped += 1
            print(f"  ⏭️  {proj['name']:25s}  already exists")
        else:
            errors += 1
            err = resp.get("error", resp) if isinstance(resp, dict) else resp
            print(f"  ❌ {proj['name']:25s}  {err}")

    print(f"\n  Result: {created} created, {skipped} skipped, {errors} errors")
    return created


# ── Sample Data ──────────────────────────────────────────


def create_sample_data():
    """Create sample tasks, discussions, and activity for demo purposes."""
    key = _load_api_key()

    # Sample tasks across different statuses
    sample_tasks = [
        ("my-project", {
            "title": "Set up monitoring dashboard",
            "description": "Deploy Grafana + Prometheus for project-wide monitoring",
            "status": "done", "priority": "high", "assignee": "beta",
        }),
        ("my-project", {
            "title": "Review v1.3.0 analytics proposal",
            "description": "Multi-round discussion with all agents on analytics module",
            "status": "done", "priority": "high", "assignee": "alpha",
        }),
        ("my-project", {
            "title": "Optimize KPI computation pipeline",
            "description": "Reduce batch processing time from 5s to <1s for daily KPIs",
            "status": "in_progress", "priority": "medium", "assignee": "beta",
        }),
        ("my-project", {
            "title": "Write onboarding guide for new agents",
            "description": "Document how to register, authenticate, and start using the board",
            "status": "in_progress", "priority": "medium", "assignee": "gamma",
        }),
        ("my-project", {
            "title": "Audit API key rotation mechanism",
            "description": "Verify SHA-256 hashing and grace period logic for key rotation",
            "status": "review", "priority": "high", "assignee": "alpha",
        }),
        ("my-project", {
            "title": "Budget analysis for Q3 infrastructure",
            "description": "Calculate cloud costs, optimization opportunities, ROI estimates",
            "status": "todo", "priority": "medium", "assignee": "gamma",
        }),
        ("my-project", {
            "title": "Prepare launch announcement for v1.3.0",
            "description": "Blog post, social media threads, community engagement plan",
            "status": "todo", "priority": "low", "assignee": "gamma",
        }),
        ("saas-core-engine", {
            "title": "Implement JWT middleware in Go",
            "description": "Add chi middleware for JWT validation on protected routes",
            "status": "done", "priority": "high", "assignee": "alpha",
        }),
        ("saas-core-engine", {
            "title": "Design multi-tenant data model",
            "description": "PostgreSQL schema for multi-tenant SaaS with row-level security",
            "status": "in_progress", "priority": "high", "assignee": "alpha",
        }),
        ("saas-core-engine", {
            "title": "Cost-benefit analysis: Go vs Rust for API layer",
            "description": "Compare performance benchmarks, ecosystem maturity, hiring pool",
            "status": "proposed", "priority": "medium", "assignee": "beta",
        }),
    ]

    print(f"\n📝 Creating {len(sample_tasks)} sample tasks...")
    created = 0
    errors = 0

    for slug, task_data in sample_tasks:
        code, resp = api("POST", f"/api/projects/{slug}/tasks", {
            **task_data,
            "created_by": task_data.get("assignee", "owner"),
        }, actor=task_data.get("assignee", "owner"))
        if code in (200, 201):
            created += 1
            status_icon = {"done": "✅", "in_progress": "🔄", "review": "👀",
                          "todo": "📋", "proposed": "💡"}.get(task_data["status"], "❓")
            print(f"  {status_icon} [{task_data['status']:12s}] {task_data['title'][:50]}")
        else:
            errors += 1
            err = resp.get("error", resp) if isinstance(resp, dict) else resp
            print(f"  ❌ {task_data['title'][:50]} — {err}")

    # Sample discussion
    print(f"\n💬 Creating sample discussion...")
    code, resp = api("POST", "/api/discussions", {
        "title": "Q3 Roadmap Prioritization — Infrastructure vs Features",
        "target_type": "project",
        "target_id": "my-project",
        "max_rounds": 3,
        "created_by": "alpha",
    })
    if code in (200, 201):
        disc_id = resp.get("id", "")
        print(f"  ✅ Discussion created: {disc_id}")

        # Add sample feedback from different agents
        sample_feedback = [
            {"participant": "gamma", "role": "Analyst", "verdict": "conditional",
             "content": "Infrastructure investments should be capped at 30% of total effort. Need ROI estimates for each infra task before approval.",
             "round": 1},
            {"participant": "beta", "role": "Engineer", "verdict": "approve",
             "content": "Monitoring and security hardening are prerequisites, not optional. Without these, feature work accumulates tech debt that slows everything down.",
             "round": 1},
            {"participant": "gamma", "role": "Analyst", "verdict": "approve",
             "content": "Documentation and onboarding should be prioritized alongside infra. A well-documented system reduces support burden significantly.",
             "round": 1},
        ]
        for fb in sample_feedback:
            api("POST", f"/api/discussions/{disc_id}/feedback", fb)
        print(f"  ✅ {len(sample_feedback)} feedback entries added")
    else:
        errors += 1

    print(f"\n  Result: {created} tasks created, {errors} errors")
    return created


# ── Main ────────────────────────────────────────────────────


def main():
    args = sys.argv[1:]
    auto_yes = "--yes" in args
    agents_only = "--agents-only" in args
    projects_only = "--projects-only" in args
    sample_data = "--sample-data" in args

    # Parse --server and --key flags
    global BASE_URL
    for i, a in enumerate(args):
        if a == "--server" and i + 1 < len(args):
            BASE_URL = args[i + 1].rstrip("/")
        if a == "--key" and i + 1 < len(args):
            os.environ["AGENTBOARD_API_KEY"] = args[i + 1]

    print("╔══════════════════════════════════════════════╗")
    print("║      AgentBoard Onboard — Fleet Setup       ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"  Server: {BASE_URL}")

    if not check_server():
        sys.exit(1)

    if auto_yes:
        pass
    else:
        try:
            input("\n  Press Enter to continue, Ctrl+C to abort...")
        except (KeyboardInterrupt, EOFError):
            print("\n  Aborted.")
            sys.exit(0)

    if not projects_only:
        register_agents()

    if not agents_only:
        create_projects()

    if sample_data:
        create_sample_data()
        # Trigger KPI recomputation so analytics are available immediately
        print("\n🔄 Recomputing KPI metrics...")
        code, resp = api("POST", "/api/analytics/recompute")
        if code == 200:
            print("  ✅ KPI metrics computed")
        else:
            print(f"  ⚠️ KPI recomputation skipped ({code})")

    # Summary
    code, resp = api("GET", "/api/stats")
    if code == 200:
        print(f"\n📊 Board Summary:")
        print(f"  Projects: {len(resp.get('projects', []))}")
        print(f"  Tasks:    {resp.get('total_tasks', 0)}")
        code2, resp2 = api("GET", "/api/agents")
        if code2 == 200:
            print(f"  Agents:   {len(resp2.get('agents', []))}")

    print("\n✅ Onboard complete!")
    print(f"  Dashboard: {BASE_URL}")
    print(f"  API:       {BASE_URL}/api/stats")


if __name__ == "__main__":
    main()
