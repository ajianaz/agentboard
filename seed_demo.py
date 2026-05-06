#!/usr/bin/env python3
"""Seed AgentBoard dev with sample data for testing."""
import json, urllib.request, sys

sys.path.insert(0, "/opt/data/agentboard-dev")
from auth import get_or_create_api_key

API = get_or_create_api_key()
BASE = "http://127.0.0.1:8766"

def api(method, path, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {API}")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}

# --- Clean up old fusion-comparison projects ---
existing = api("GET", "/api/projects")
for p in existing.get("projects", []):
    if p.get("slug", "").startswith("fusion-comparison"):
        api("DELETE", f"/api/projects/{p['slug']}")
        print(f"  Deleted old project: {p['slug']}")

# --- PROJECT ---
demo = api("POST", "/api/projects", {
    "name": "Fusion Comparison",
    "slug": "fusion-comparison",
    "description": "Feature comparison: Runfusion/Fusion vs AgentBoard",
    "icon": "🔬",
    "color": "#8b5cf6"
})
proj = demo.get("project", demo)
proj_id = proj.get("id")
proj_slug = proj.get("slug", "fusion-comparison")
print(f"Project: {proj.get('name')} (slug={proj_slug}, id={proj_id})")
if not proj_id:
    print("FAILED to create project")
    sys.exit(1)

# --- TASKS ---
sample_tasks = [
    {"title": "Setup dev environment", "status": "done", "priority": "high",
     "assignee": "owner", "tags": ["setup"],
     "description": "Install dependencies, configure database, verify server starts correctly."},
    {"title": "Compare architecture patterns", "status": "in_progress", "priority": "critical",
     "assignee": "zeko", "tags": ["research", "architecture"],
     "description": "Analyze Fusion's modular architecture vs AgentBoard's monolithic stdlib approach."},
    {"title": "Evaluate agent routing model", "status": "in_progress", "priority": "high",
     "assignee": "zeko", "tags": ["agents", "routing"],
     "description": "Compare how Fusion routes tasks to agents vs our queue-based routing."},
    {"title": "Analyze tool/plugin system", "status": "todo", "priority": "medium",
     "assignee": "cto", "tags": ["tools", "plugins"],
     "description": "Evaluate Fusion's MCP integration vs our custom tool system."},
    {"title": "Compare database schemas", "status": "todo", "priority": "medium",
     "assignee": "zeko", "tags": ["database"],
     "description": "Map Fusion's data model to AgentBoard's SQLite schema."},
    {"title": "Evaluate API design patterns", "status": "todo", "priority": "medium",
     "assignee": "cto", "tags": ["api"],
     "description": "REST vs their approach — compare endpoint design and response formats."},
    {"title": "Test multi-agent orchestration", "status": "todo", "priority": "high",
     "assignee": "kai", "tags": ["agents", "testing"],
     "description": "Run parallel agent tasks and compare coordination overhead."},
    {"title": "Review auth & security model", "status": "proposed", "priority": "medium",
     "assignee": "", "tags": ["security", "auth"],
     "description": "Audit Fusion's auth approach vs our API key system."},
    {"title": "Write comparison report", "status": "proposed", "priority": "low",
     "assignee": "", "tags": ["docs", "report"],
     "description": "Compile findings into structured comparison document."},
    {"title": "Benchmark performance", "status": "proposed", "priority": "low",
     "assignee": "", "tags": ["performance"],
     "description": "Load test both systems with 1000+ tasks."},
    {"title": "Assess UI/UX approach", "status": "todo", "priority": "low",
     "assignee": "sosmed", "tags": ["ui", "ux"],
     "description": "Compare Fusion's frontend tech stack vs our vanilla JS SPA."},
    {"title": "Evaluate real-time features", "status": "todo", "priority": "high",
     "assignee": "cto", "tags": ["realtime", "sse"],
     "description": "Compare real-time update mechanisms (SSE/WebSocket) between both systems."},
]

created = 0
for t in sample_tasks:
    t["type"] = "task"
    result = api("POST", f"/api/projects/{proj_slug}/tasks", t)
    if "error" not in result:
        created += 1
        print(f"  ✓ {t['title']}")
    else:
        print(f"  ✗ {t['title']}: {result}")

print(f"\nTasks: {created}/{len(sample_tasks)} created")

# --- DISCUSSION ---
disc = api("POST", "/api/discussions", {
    "title": "Fusion vs AgentBoard — Architecture Decision",
    "context": "Comparing Runfusion/Fusion with our AgentBoard to evaluate patterns worth adopting.",
    "participants": ["zeko", "cto"],
    "leader": "zeko",
    "max_rounds": 3
})
print(f"Discussion: {'✓' if 'error' not in disc else '✗ ' + str(disc)}")

print("\n✅ Seed complete!")
