"""AgentBoard — Webhook notification system.

Sends async notifications to Hermes agent gateways when tasks change.
Uses Python stdlib only (urllib.request + threading).

Events:
    task.created    — new task created with assignee
    task.assigned   — task reassigned to different agent
    task.status     — task status changed
    task.comment    — comment added to task
    task.approved   — owner approved proposed task
    task.rejected   — owner rejected proposed task
"""

import json
import logging
import threading
import urllib.error
import urllib.request
from config import get_config

logger = logging.getLogger(__name__)

# Agent ID → Hermes gateway port mapping
DEFAULT_AGENT_PORTS = {
    "cto": 8647,
    "zeko": 8648,
    "cfo": 8645,
    "kai": 8650,
    "sosmed": 8651,
    "badsector": 8652,
    "nova": 8649,
}


def _get_agent_ports() -> dict:
    """Get agent→port mapping from config, falling back to defaults."""
    cfg = get_config()
    webhook_cfg = cfg.get("webhooks", {})
    return webhook_cfg.get("agent_ports", DEFAULT_AGENT_PORTS)


def _is_webhook_enabled() -> bool:
    """Check if webhook notifications are enabled."""
    cfg = get_config()
    return cfg.get("webhooks", {}).get("enabled", False)


def _get_webhook_timeout() -> int:
    """Get webhook request timeout in seconds."""
    cfg = get_config()
    return cfg.get("webhooks", {}).get("timeout", 5)


def notify_agent(agent_id: str, event: str, payload: dict):
    """Send a webhook notification to an agent's gateway.

    Runs in a background thread to avoid blocking the API response.

    Args:
        agent_id: Target agent ID (e.g., 'cto', 'kai').
        event: Event type (e.g., 'task.assigned', 'task.status').
        payload: Event data dict — will be wrapped in an envelope.
    """
    if not _is_webhook_enabled():
        return

    if not agent_id:
        return

    # Fire in background thread
    t = threading.Thread(
        target=_send_webhook,
        args=(agent_id, event, payload),
        daemon=True,
    )
    t.start()


def _send_webhook(agent_id: str, event: str, payload: dict):
    """Actually send the webhook. Called from background thread."""
    ports = _get_agent_ports()
    port = ports.get(agent_id)

    if not port:
        logger.debug("No port configured for agent '%s', skipping webhook", agent_id)
        return

    url = f"http://127.0.0.1:{port}/webhooks/agentboard"

    envelope = {
        "event": event,
        "agent_id": agent_id,
        "timestamp": _utc_now(),
        "data": payload,
    }

    body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    timeout = _get_webhook_timeout()

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            if status >= 400:
                logger.warning(
                    "Webhook to %s returned %d for event %s",
                    agent_id, status, event,
                )
            else:
                logger.debug(
                    "Webhook to %s OK (%d) for event %s",
                    agent_id, status, event,
                )
    except urllib.error.HTTPError as e:
        logger.warning(
            "Webhook to %s failed: HTTP %d for event %s",
            agent_id, e.code, event,
        )
    except urllib.error.URLError as e:
        logger.warning(
            "Webhook to %s failed: %s for event %s",
            agent_id, e.reason, event,
        )
    except Exception as e:
        logger.error(
            "Webhook to %s error: %s for event %s",
            agent_id, e, event,
        )


def _utc_now() -> str:
    """Return current UTC time in ISO 8601 format."""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Convenience helpers — call from task handlers
# ---------------------------------------------------------------------------

def on_task_created(task: dict, actor: str, project_slug: str):
    """Fire webhook when a task is created with an assignee."""
    if task.get("assignee"):
        notify_agent(task["assignee"], "task.created", {
            "task_id": task["id"],
            "title": task["title"],
            "status": task.get("status", "todo"),
            "priority": task.get("priority", "none"),
            "project": project_slug,
            "created_by": actor,
        })


def on_task_assigned(task: dict, old_assignee: str, new_assignee: str,
                     actor: str, project_slug: str):
    """Fire webhook when a task is reassigned."""
    payload = {
        "task_id": task["id"],
        "title": task["title"],
        "status": task.get("status", "todo"),
        "project": project_slug,
        "reassigned_by": actor,
        "from_agent": old_assignee or "(unassigned)",
        "to_agent": new_assignee,
    }
    # Notify old assignee (removed from task)
    if old_assignee and old_assignee != new_assignee:
        notify_agent(old_assignee, "task.unassigned", payload)
    # Notify new assignee
    notify_agent(new_assignee, "task.assigned", payload)


def on_task_status_changed(task: dict, old_status: str, new_status: str,
                           actor: str, project_slug: str):
    """Fire webhook when a task status changes."""
    # Determine the most relevant event name
    event = "task.status"
    if (old_status, new_status) == ("proposed", "todo"):
        event = "task.approved"
    elif new_status == "rejected":
        event = "task.rejected"
    elif (old_status, new_status) == ("repurposed", "todo"):
        event = "task.repurposed"

    payload = {
        "task_id": task["id"],
        "title": task["title"],
        "from_status": old_status,
        "to_status": new_status,
        "project": project_slug,
        "changed_by": actor,
    }

    # Always notify assignee
    if task.get("assignee"):
        notify_agent(task["assignee"], event, payload)


def on_task_comment(task: dict, comment_author: str, comment_text: str,
                    project_slug: str):
    """Fire webhook when a comment is added to a task."""
    payload = {
        "task_id": task["id"],
        "title": task["title"],
        "comment_by": comment_author,
        "comment_preview": comment_text[:200],
        "project": project_slug,
    }
    # Notify assignee (but not the commenter themselves)
    assignee = task.get("assignee")
    if assignee and assignee != comment_author:
        notify_agent(assignee, "task.comment", payload)
