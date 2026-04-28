"""AgentBoard — Webhook notification system.

Sends async notifications to agent gateways when tasks or discussions change.
Uses Python stdlib only (urllib.request + threading).

Events:
    task.created    — new task created with assignee
    task.assigned   — task reassigned to different agent
    task.status     — task status changed
    task.comment    — comment added to task
    task.approved   — owner approved proposed task
    task.rejected   — owner rejected proposed task
    discussion.created   — new discussion created with participants
    discussion.feedback  — feedback submitted for a discussion round
    discussion.closed    — discussion closed or reached consensus
"""

import hashlib
import hmac
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from config import get_config

logger = logging.getLogger(__name__)

# Agent ID → gateway port mapping (Hermes fleet)
# Override via config: webhooks.agent_ports in agentboard.toml
DEFAULT_AGENT_PORTS = {
    "zeko": 8648,
    "cfo": 8645,
    "cto": 8647,
    "badsector": 8652,
    "kai": 8650,
    "sosmed": 8651,
    "novelist": 8649,
}


def _get_agent_ports() -> dict:
    """Get agent→port mapping from config, falling back to defaults."""
    cfg = get_config()
    webhook_cfg = cfg.get("webhooks", {})
    return webhook_cfg.get("agent_ports", DEFAULT_AGENT_PORTS)


def _get_webhook_secret() -> str:
    """Get HMAC secret for webhook signing.

    Priority: env var WEBHOOK_SECRET > config > .env file.
    In Docker, the secret is injected via compose environment.
    On host/dev, falls back to /opt/data/.env file.
    """
    # 1. Process environment variable (Docker compose injects this)
    env_secret = os.environ.get("WEBHOOK_SECRET", "")
    if env_secret:
        return env_secret
    # 2. Config file
    cfg = get_config()
    secret = cfg.get("webhooks", {}).get("secret", "")
    if secret:
        return secret
    # 3. .env file (host/dev mode)
    env_path = "/opt/data/.env"
    if os.path.exists(env_path):
        try:
            with open(env_path) as f:
                for line in f:
                    if line.startswith("WEBHOOK_SECRET="):
                        return line.strip().split("=", 1)[1]
        except OSError:
            pass
    return ""


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


def _is_docker() -> bool:
    """Detect if running inside a Docker container."""
    return os.path.exists("/.dockerenv")


def _get_agent_url(agent_id: str) -> str | None:
    """Build the direct webhook URL for an agent's gateway.

    Docker: delivers directly to host.docker.internal:{port}/webhooks/agentboard.
            Requires agent gateway to bind 0.0.0.0 (not 127.0.0.1).
    Host/dev: delivers directly to 127.0.0.1:{port}/webhooks/agentboard.

    Returns None if agent_id has no known port mapping.
    """
    ports = _get_agent_ports()
    port = ports.get(agent_id)
    if not port:
        return None

    if _is_docker():
        return f"http://host.docker.internal:{port}/webhooks/agentboard"
    else:
        return f"http://127.0.0.1:{port}/webhooks/agentboard"


def _send_webhook(agent_id: str, event: str, payload: dict):
    """Actually send the webhook. Called from background thread."""
    url = _get_agent_url(agent_id)
    if not url:
        logger.warning(
            "Webhook to %s skipped: no port mapping for agent", agent_id
        )
        return

    import uuid as _uuid
    envelope = {
        "event": event,
        "event_id": _uuid.uuid4().hex[:16],
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

    # HMAC-SHA256 signature (matches Hermes gateway webhook verification)
    secret = _get_webhook_secret()
    if secret:
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        req.add_header("X-Hub-Signature-256", f"sha256={signature}")
    else:
        logger.warning(
            "Webhook to %s sent WITHOUT HMAC signature — WEBHOOK_SECRET not configured",
            agent_id,
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


# ---------------------------------------------------------------------------
# Discussion webhook helpers — call from discussion handlers
# ---------------------------------------------------------------------------

def on_discussion_created(discussion: dict, actor: str):
    """Fire webhook to all participants when a new discussion is created."""
    participants = discussion.get("participants", [])
    if isinstance(participants, str):
        try:
            participants = json.loads(participants)
        except (json.JSONDecodeError, ValueError):
            participants = []

    payload = {
        "discussion_id": discussion["id"],
        "title": discussion["title"],
        "status": discussion.get("status", "open"),
        "target_type": discussion.get("target_type", ""),
        "target_id": discussion.get("target_id", ""),
        "current_round": discussion.get("current_round", 1),
        "max_rounds": discussion.get("max_rounds", 5),
        "created_by": actor,
        "leader": discussion.get("leader", ""),
        "context": (discussion.get("context", "") or "")[:500],
    }

    for participant in participants:
        if isinstance(participant, str):
            participant_id = participant.strip()
        elif isinstance(participant, dict):
            participant_id = participant.get("id", participant.get("name", "")).strip()
        else:
            continue
        if participant_id and participant_id != actor:
            notify_agent(participant_id, "discussion.created", payload)


def on_discussion_feedback(discussion: dict, feedback: dict, actor: str):
    """Fire webhook to discussion leader and other participants when feedback is submitted."""
    participants = discussion.get("participants", [])
    if isinstance(participants, str):
        try:
            participants = json.loads(participants)
        except (json.JSONDecodeError, ValueError):
            participants = []

    payload = {
        "discussion_id": discussion["id"],
        "title": discussion["title"],
        "current_round": discussion.get("current_round", 1),
        "max_rounds": discussion.get("max_rounds", 5),
        "feedback_by": feedback.get("participant", actor),
        "feedback_verdict": feedback.get("verdict", ""),
        "feedback_round": feedback.get("round", 1),
        "feedback_preview": (feedback.get("content", "") or "")[:200],
    }

    # Notify leader
    leader = discussion.get("leader", "")
    if leader and leader != actor:
        notify_agent(leader, "discussion.feedback", payload)

    # Notify other participants (not the feedback author)
    for participant in participants:
        if isinstance(participant, str):
            participant_id = participant.strip()
        elif isinstance(participant, dict):
            participant_id = participant.get("id", participant.get("name", "")).strip()
        else:
            continue
        if participant_id and participant_id != actor and participant_id != leader:
            notify_agent(participant_id, "discussion.feedback", payload)


def on_discussion_closed(discussion: dict, actor: str):
    """Fire webhook to all participants when a discussion is closed or reaches consensus."""
    participants = discussion.get("participants", [])
    if isinstance(participants, str):
        try:
            participants = json.loads(participants)
        except (json.JSONDecodeError, ValueError):
            participants = []

    payload = {
        "discussion_id": discussion["id"],
        "title": discussion["title"],
        "status": discussion.get("status", "closed"),
        "current_round": discussion.get("current_round", 1),
        "closed_by": actor,
    }

    for participant in participants:
        if isinstance(participant, str):
            participant_id = participant.strip()
        elif isinstance(participant, dict):
            participant_id = participant.get("id", participant.get("name", "")).strip()
        else:
            continue
        if participant_id:
            notify_agent(participant_id, "discussion.closed", payload)
