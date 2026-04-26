# AgentBoard Tools

Standalone utility scripts for AgentBoard. Zero pip dependencies — Python 3.11+ stdlib only.

## client.py

Minimal API client for AgentBoard's REST API.

```python
from tools.client import tasks, create_task, update_task

result = tasks("my-project", status="todo")
t = create_task("my-project", title="Fix login bug", priority="high", assignee="dev-1")
```

### Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `AGENTBOARD_URL` | Server URL | `http://localhost:8765` |
| `AGENTBOARD_API_KEY` | API key for write ops | `""` (reads `.api_key` file) |
| `AGENTBOARD_KEY_FILE` | Path to API key file | `../.api_key` (relative to tools/) |

## discussion.py

Multi-agent discussion coordinator. Sends review requests to agents and collects feedback.

```python
from tools.discussion import DiscussionSession

def my_send_fn(agent, payload):
    """Your transport implementation — webhook, API call, message queue, etc."""
    import urllib.request, json
    url = f"http://your-agent-gateway/{agent}/webhooks/discussion"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    resp = urllib.request.urlopen(req, timeout=15)
    return resp.status == 200

disc = DiscussionSession(
    topic="Feature Review — Auth Module",
    leader="dev-1",
    participants=["dev-2", "qa-1"],
    max_rounds=2,
)
disc.create()
disc.write_leader_draft("# Draft\n...\n")
sent = disc.send_round_request(send_fn=my_send_fn)
feedback = disc.collect_feedback(timeout=60)
disc.write_synthesis("# Synthesis\n...\n")
disc.close()
```

### Transport Configuration

**Option A: Inject send function** (recommended)
Pass `send_fn` to `send_round_request()`. Full control over delivery.

**Option B: Config file**
Create `discussion_config.json` alongside this file:
```json
{
  "endpoints": {
    "agent-1": "http://localhost:8100/webhooks/discussion",
    "agent-2": "http://localhost:8101/webhooks/discussion"
  },
  "hmac_key": "your-optional-hmac-key"
}
```

### CLI

```bash
python -m tools.discussion create --topic "Review" --leader dev-1 --participants dev-2,qa-1
python -m tools.discussion list
python -m tools.discussion status <session-id>
```
