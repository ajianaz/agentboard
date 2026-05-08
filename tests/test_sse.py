"""Tests for SSE event bus and SSE endpoint."""

import json
import queue
import threading
import time
import unittest

# Import event_bus before server (circular risk)
from event_bus import publish, subscribe, unsubscribe, get_buffer, subscriber_count, _event_buffer, _sub_lock


class TestEventBus(unittest.TestCase):
    """Test the in-process event bus pub/sub."""

    def setUp(self):
        # Clear buffer between tests
        with _sub_lock:
            _event_buffer.clear()

    def test_publish_single_subscriber(self):
        """A subscriber should receive published events."""
        q = subscribe()
        try:
            publish("task_created", {"id": "abc", "title": "Test"})
            msg = q.get(timeout=1)
            self.assertIn("event: task_created", msg)
            self.assertIn('"id": "abc"', msg)
        finally:
            unsubscribe(q)

    def test_publish_multiple_subscribers(self):
        """Multiple subscribers should all receive the same event."""
        q1 = subscribe()
        q2 = subscribe()
        try:
            publish("plan_updated", {"id": "p1"})
            self.assertEqual(q1.get(timeout=1), q2.get(timeout=1))
        finally:
            unsubscribe(q1)
            unsubscribe(q2)

    def test_buffer_for_late_joiners(self):
        """New subscribers should receive buffered events via get_buffer()."""
        publish("task_created", {"id": "early"})
        msgs = get_buffer()
        self.assertEqual(len(msgs), 1)
        self.assertIn("task_created", msgs[0])

    def test_buffer_max_size(self):
        """Buffer should not exceed BUFFER_MAX."""
        from event_bus import _BUFFER_MAX
        for i in range(_BUFFER_MAX + 20):
            publish("test", {"i": i})
        with _sub_lock:
            self.assertLessEqual(len(_event_buffer), _BUFFER_MAX)

    def test_subscriber_count(self):
        """subscriber_count should reflect active subscriptions."""
        q = subscribe()
        try:
            self.assertGreaterEqual(subscriber_count(), 1)
        finally:
            unsubscribe(q)

    def test_unsubscribe(self):
        """Unsubscribed queue should no longer receive events."""
        q = subscribe()
        unsubscribe(q)
        publish("test", {"after": "unsubscribe"})
        self.assertTrue(q.empty())

    def test_event_format(self):
        """Events should be in proper SSE format: event: ...\ndata: ...\n\n."""
        q = subscribe()
        try:
            publish("task_deleted", {"id": "t1"})
            msg = q.get(timeout=1)
            lines = msg.strip().split("\n")
            self.assertEqual(lines[0], "event: task_deleted")
            self.assertTrue(lines[1].startswith("data: {"))
            # Parse JSON from data line
            data = json.loads(lines[1][6:])
            self.assertEqual(data["type"], "task_deleted")
            self.assertEqual(data["payload"]["id"], "t1")
            self.assertIn("ts", data)
        finally:
            unsubscribe(q)

    def test_concurrent_publish(self):
        """Multiple threads publishing should not crash."""
        errors = []

        def publisher(n):
            try:
                for i in range(50):
                    publish("concurrent_test", {"n": n, "i": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=publisher, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        self.assertEqual(errors, [])


class TestSSEEndpoint(unittest.TestCase):
    """Test the /api/events SSE endpoint."""

    def setUp(self):
        # Clear buffer
        with _sub_lock:
            _event_buffer.clear()

    def test_sse_handler_exists(self):
        """SSE handler method should exist on RequestHandler."""
        from server import RequestHandler
        self.assertTrue(hasattr(RequestHandler, '_handle_sse'))


if __name__ == "__main__":
    unittest.main()
