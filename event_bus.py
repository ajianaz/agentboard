"""AgentBoard — Lightweight SSE event bus.

Thread-safe pub/sub for real-time board updates. Uses only stdlib.
Events are published from API handlers and broadcast to all connected
SSE clients via /api/events endpoint.

Usage (publisher — from API handler):
    from event_bus import publish
    publish("task_updated", {"id": task_id, "project": slug})

Usage (consumer — SSE clients connect to GET /api/events):
    Event stream delivers: "event: task_updated\\ndata: {...}\\n\\n"
"""

import json
import threading
import time
import queue

# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

_subscribers: list[queue.Queue] = []
_sub_lock = threading.Lock()
_event_buffer: list[dict] = []       # ring buffer for late joiners
_BUFFER_MAX = 50


def publish(event_type: str, payload: dict):
    """Publish an event to all connected SSE subscribers.

    Args:
        event_type: Event type string (e.g. "task_updated", "plan_created").
        payload: Dict with event data. Must be JSON-serializable.
    """
    data = {
        "type": event_type,
        "payload": payload,
        "ts": time.time(),
    }

    # Buffer for late joiners
    with _sub_lock:
        _event_buffer.append(data)
        if len(_event_buffer) > _BUFFER_MAX:
            _event_buffer.pop(0)

    msg = _format_sse(data)

    with _sub_lock:
        for q in list(_subscribers):
            try:
                q.put_nowait(msg)
            except queue.Full:
                # Subscriber too slow — drop event
                pass


def subscribe() -> queue.Queue:
    """Subscribe to events. Returns a Queue that receives SSE-formatted strings."""
    q: queue.Queue = queue.Queue(maxsize=100)
    with _sub_lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue):
    """Remove a subscriber queue."""
    with _sub_lock:
        if q in _subscribers:
            _subscribers.remove(q)


def get_buffer() -> list[str]:
    """Get buffered events for a new subscriber (catch-up)."""
    with _sub_lock:
        return [_format_sse(e) for e in _event_buffer]


def subscriber_count() -> int:
    """Return number of active SSE subscribers."""
    with _sub_lock:
        return len(_subscribers)


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _format_sse(data: dict) -> str:
    """Format a dict as an SSE message string."""
    return f"event: {data['type']}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
