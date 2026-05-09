"""Tests for AgentBoard rate limiter module."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestRateLimiter:
    """Test rate_limiter.py — sliding window rate limiter."""

    def test_basic_allow(self):
        """First request should always be allowed."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=60, burst=10)
        assert rl.check("key-1") is True

    def test_window_limit(self):
        """Requests should be blocked after exceeding window limit."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=3, burst=10, window_seconds=60)
        assert rl.check("key-2") is True
        assert rl.check("key-2") is True
        assert rl.check("key-2") is True
        assert rl.check("key-2") is False  # 4th request blocked

    def test_burst_limit(self):
        """Requests should be blocked after exceeding burst limit per second."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=100, burst=2, window_seconds=60)
        assert rl.check("key-3") is True
        assert rl.check("key-3") is True
        assert rl.check("key-3") is False  # 3rd request in same second blocked

    def test_unlimited_key(self):
        """Key with rate_limit=0 should never be rate limited."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=3, burst=2)
        rl.set_key_limit("unlimited-key", 0)
        for _ in range(100):
            assert rl.check("unlimited-key") is True

    def test_per_key_limit(self):
        """Per-key limit override should work independently."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=100, burst=10)
        rl.set_key_limit("restricted-key", 2)
        assert rl.check("restricted-key") is True
        assert rl.check("restricted-key") is True
        assert rl.check("restricted-key") is False
        # Other keys should still have default limit
        assert rl.check("other-key") is True

    def test_isolated_keys(self):
        """Different keys should have independent counters."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=2, burst=10, window_seconds=60)
        assert rl.check("key-a") is True
        assert rl.check("key-a") is True
        assert rl.check("key-a") is False  # key-a exhausted
        assert rl.check("key-b") is True   # key-b still has capacity

    def test_retry_after(self):
        """retry_after should return positive int when rate limited."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=1, burst=10, window_seconds=60)
        rl.check("key-ra")
        rl.check("key-ra")  # will be blocked
        retry = rl.retry_after("key-ra")
        assert retry > 0
        assert retry <= 60

    def test_retry_after_unlimited(self):
        """retry_after should return 0 for unlimited keys."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=3)
        rl.set_key_limit("unlimited", 0)
        assert rl.retry_after("unlimited") == 0

    def test_get_headers(self):
        """get_headers should return X-RateLimit-* dict."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=100, burst=10)
        headers = rl.get_headers("key-h")
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    def test_get_headers_unlimited(self):
        """get_headers for unlimited key should return 'unlimited'."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=100)
        rl.set_key_limit("unlimited", 0)
        headers = rl.get_headers("unlimited")
        assert headers["X-RateLimit-Limit"] == "unlimited"
        assert headers["X-RateLimit-Remaining"] == "unlimited"

    def test_reset(self):
        """reset should clear counter for a key."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=1, burst=10)
        rl.check("key-reset")
        assert rl.check("key-reset") is False
        rl.reset("key-reset")
        assert rl.check("key-reset") is True

    def test_get_effective_limit(self):
        """get_effective_limit should return per-key override or default."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=50)
        assert rl.get_effective_limit("normal") == 50
        rl.set_key_limit("custom", 100)
        assert rl.get_effective_limit("custom") == 100
        rl.set_key_limit("unlim", 0)
        assert rl.get_effective_limit("unlim") == 0

    def test_set_key_limit_remove_override(self):
        """Setting rate_limit to 0 should mark key as unlimited."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=10)
        rl.set_key_limit("key", 5)
        assert rl.get_effective_limit("key") == 5
        rl.set_key_limit("key", 0)  # set to unlimited
        assert rl.get_effective_limit("key") == 0  # 0 = unlimited

    def test_cleanup(self):
        """Cleanup should remove expired entries."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=1, burst=10, window_seconds=1, cleanup_interval=1)
        rl.check("expire-key")
        rl.check("expire-key")  # blocked
        time.sleep(2.5)
        rl._cleanup()
        # After cleanup, bucket should be gone
        assert "expire-key" not in rl._buckets

    def test_stop(self):
        """stop() should terminate cleanup thread without error."""
        from rate_limiter import RateLimiter
        rl = RateLimiter(default_limit=60)
        rl.stop()
        # Should not raise
        rl.stop()  # idempotent

    def test_thread_safety(self):
        """Concurrent checks should not corrupt state."""
        from rate_limiter import RateLimiter
        import threading
        rl = RateLimiter(default_limit=1000, burst=100)
        errors = []

        def check_key(n):
            try:
                for _ in range(100):
                    rl.check(f"thread-{n}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check_key, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0, f"Thread safety errors: {errors}"
