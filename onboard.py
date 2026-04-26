#!/usr/bin/env python3
"""AgentBoard Onboard — registers default agent fleet and creates starter projects.

Usage:
    python onboard.py                    # Interactive (asks for confirmation)
    python onboard.py --yes              # Non-interactive (auto-confirm)
    python onboard.py --agents-only      # Only register agents
    python onboard.py --projects-only    # Only create projects

Run after `git clone` and `python server.py` (first run auto-generates .api_key).
"""

import json
import os
import sys
import urllib.request
import urllib.error

# ── Config ──────────────────────────────────────────────────

BASE_URL = os.environ.get("AGENTBOARD_URL", "http://127.0.0.1:8765")
API_KEY_FILE = os.environ.get("AGENTBOARD_API_KEY_FILE", ".api_key")

DEFAULT_AGENTS = [
    {
        "id": "cto",
        "name": "CTO",
        "role": "Chief Technology Officer — System Analyst, Architect",
        "avatar": "🏗️",
        "color": "#3b82f6",
    },
    {
        "id": "zeko",
        "name": "Zeko",
        "role": "DevOps & Security — System Orchestration, Patrol, CS",
        "avatar": "🛡️",
        "color": "#ef4444",
    },
    {
        "id": "cfo",
        "name": "CFO",
        "role": "Chief Financial Officer — Finance, Revenue, Ops",
        "avatar": "💰",
        "color": "#22c55e",
    },
    {
        "id": "kai",
        "name": "Kai",
        "role": "Content Creator — Writing, Blog, Newsletter",
        "avatar": "✍️",
        "color": "#f59e0b",
    },
    {
        "id": "somad",
        "name": "Somad",
        "role": "Social Media Manager — Distribution, Engagement",
        "avatar": "📱",
        "color": "#8b5cf6",
    },
    {
        "id": "bad-sector",
        "name": "Bad Sector",
        "role": "Devil's Advocate — Critical Review, Challenge Ideas",
        "avatar": "😈",
        "color": "#dc2626",
    },
    {
        "id": "nova",
        "name": "Nova",
        "role": "Novelist — Creative Writing (Parked)",
        "avatar": "📖",
        "color": "#06b6d4",
    },
]

DEFAULT_PROJECTS = [
    {
        "name": "Hermes Fleet",
        "icon": "🏗️",
        "color": "#3b82f6",
        "description": "Fleet-wide coordination, infrastructure, and cross-agent tasks",
    },
    {
        "name": "SaaS Core Engine",
        "icon": "⚙️",
        "color": "#f97316",
        "description": "Go-based SaaS engine — backend, CLI, web templates",
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


def api(method: str, path: str, data: dict = None) -> tuple:
    """Make API call. Returns (status_code, response_dict_or_str)."""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    key = _load_api_key()
    if key:
        req.add_header("Authorization", f"Bearer {key}")
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


# ── Main ────────────────────────────────────────────────────


def main():
    args = set(sys.argv[1:])
    auto_yes = "--yes" in args
    agents_only = "--agents-only" in args
    projects_only = "--projects-only" in args

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
