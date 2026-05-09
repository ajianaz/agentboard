"""rate_limiter.py — In-memory sliding window rate limiter for AgentBoard.

Tracks request counts per API key (and optional per-IP) using a fixed-window
counter that auto-expires. Zero external dependencies — pure Python dict + time.

Usage:
    from rate_limiter import RateLimiter

    limiter = RateLimiter(default_limit=60, burst=10)

    # Check if request is allowed
    allowed = limiter.check("key_id_abc")
    if not allowed:
        retry_after = limiter.retry_after("key_id_abc")
"""

import threading
import time

# Sentinel value: rate_limit=0 in DB means unlimited
_UNLIMITED = 0


class RateLimiter:
    """Thread-safe in-memory sliding window rate limiter.

    Each key_id gets a counter that resets after `window_seconds`.
    A burst check prevents more than `burst` requests in any 1-second period.
    """

    def __init__(self, default_limit: int = 60, burst: int = 10,
                 window_seconds: int = 60, cleanup_interval: int = 60):
        """Initialize rate limiter.

        Args:
            default_limit: Max requests per window per key (0 = unlimited).
            burst: Max requests in any 1-second period.
            window_seconds: Window duration in seconds.
            cleanup_interval: Seconds between stale entry cleanup.
        """
        self.default_limit = default_limit
        self.burst = burst
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval

        # {key_id: {"count": int, "window_start": float, "second_count": int, "second_start": float}}
        self._buckets: dict = {}
        self._lock = threading.Lock()

        # Per-key overrides: {key_id: limit} — 0 means unlimited
        self._key_limits: dict = {}

        # Start background cleanup thread
        self._stop_event = threading.Event()
        self._cleaner = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleaner.start()

    def set_key_limit(self, key_id: str, limit: int):
        """Set per-key rate limit override. 0 = unlimited (stored as override)."""
        with self._lock:
            self._key_limits[key_id] = limit

    def get_effective_limit(self, key_id: str) -> int:
        """Get the effective rate limit for a key."""
        with self._lock:
            return self._key_limits.get(key_id, self.default_limit)

    def check(self, key_id: str) -> bool:
        """Check if a request from key_id is allowed.

        Returns True if the request should be allowed, False if rate limited.
        This is NOT idempotent — each call increments the counter.
        """
        limit = self.get_effective_limit(key_id)
        if limit == _UNLIMITED:
            return True

        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key_id)

            if bucket is None or (now - bucket["window_start"]) >= self.window_seconds:
                # New window
                self._buckets[key_id] = {
                    "count": 1,
                    "window_start": now,
                    "second_count": 1,
                    "second_start": now,
                }
                return True

            # Check window limit
            if bucket["count"] >= limit:
                return False

            # Check burst limit (per-second)
            if now - bucket["second_start"] >= 1.0:
                bucket["second_count"] = 0
                bucket["second_start"] = now

            if bucket["second_count"] >= self.burst:
                return False

            # Allow request
            bucket["count"] += 1
            bucket["second_count"] += 1
            return True

    def retry_after(self, key_id: str) -> int:
        """Get seconds until the key can make another request."""
        limit = self.get_effective_limit(key_id)
        if limit == _UNLIMITED:
            return 0

        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key_id)
            if bucket is None:
                return 0

            window_remaining = self.window_seconds - (now - bucket["window_start"])
            second_remaining = 1.0 - (now - bucket["second_start"])

            if window_remaining <= 0 and second_remaining <= 0:
                return 0

            return max(1, int(max(window_remaining, second_remaining)))

    def get_headers(self, key_id: str) -> dict:
        """Get X-RateLimit-* headers for a response."""
        limit = self.get_effective_limit(key_id)
        if limit == _UNLIMITED:
            return {
                "X-RateLimit-Limit": "unlimited",
                "X-RateLimit-Remaining": "unlimited",
                "X-RateLimit-Reset": "0",
            }

        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key_id)
            if bucket is None:
                remaining = limit
                reset_at = int(now + self.window_seconds)
            else:
                remaining = max(0, limit - bucket["count"])
                reset_at = int(bucket["window_start"] + self.window_seconds)

        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_at),
        }

    def reset(self, key_id: str):
        """Reset rate limit counter for a key (e.g., after testing)."""
        with self._lock:
            self._buckets.pop(key_id, None)

    def _cleanup_loop(self):
        """Background thread: periodically remove expired entries."""
        while not self._stop_event.wait(self.cleanup_interval):
            self._cleanup()

    def _cleanup(self):
        """Remove expired buckets to prevent memory growth."""
        now = time.time()
        with self._lock:
            expired = [
                kid for kid, b in self._buckets.items()
                if (now - b["window_start"]) >= self.window_seconds * 2
            ]
            for kid in expired:
                del self._buckets[kid]

    def stop(self):
        """Stop the cleanup thread. Call on shutdown."""
        self._stop_event.set()
