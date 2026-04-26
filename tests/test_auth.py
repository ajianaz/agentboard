"""Tests for AgentBoard auth module."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestAuth:
    """Test auth.py — key generation, hashing, validation."""

    def test_generate_api_key_has_prefix(self):
        """API key should start with 'ab_' prefix."""
        from auth import generate_api_key
        key = generate_api_key()
        assert key.startswith("ab_"), f"Key should start with ab_, got: {key[:5]}"
        assert len(key) > 10, "Key should be reasonably long"

    def test_hash_key_deterministic(self):
        """Hashing the same key should produce the same hash."""
        from auth import hash_key
        h1 = hash_key("test-key")
        h2 = hash_key("test-key")
        assert h1 == h2, "Same key should produce same hash"

    def test_hash_key_different_for_different_keys(self):
        """Different keys should produce different hashes."""
        from auth import hash_key
        h1 = hash_key("key-one")
        h2 = hash_key("key-two")
        assert h1 != h2, "Different keys should produce different hashes"

    def test_validate_key_correct(self):
        """validate_key should return True for correct key."""
        from auth import validate_key, hash_key
        raw = "my-secret-key"
        stored = hash_key(raw)
        assert validate_key(raw, stored) is True

    def test_validate_key_incorrect(self):
        """validate_key should return False for wrong key."""
        from auth import validate_key, hash_key
        stored = hash_key("correct-key")
        assert validate_key("wrong-key", stored) is False

    def test_check_auth_no_hash(self):
        """check_auth should return True when no stored hash (first-run)."""
        from auth import check_auth
        assert check_auth({}, "") is True

    def test_check_auth_with_bearer(self):
        """check_auth should validate Bearer token."""
        from auth import check_auth, hash_key
        stored = hash_key("valid-key")
        headers = {"authorization": "Bearer valid-key"}
        assert check_auth(headers, stored) is True

    def test_check_auth_wrong_bearer(self):
        """check_auth should reject wrong Bearer token."""
        from auth import check_auth, hash_key
        stored = hash_key("correct-key")
        headers = {"authorization": "Bearer wrong-key"}
        assert check_auth(headers, stored) is False

    def test_check_auth_missing_header(self):
        """check_auth should return False when auth header is missing."""
        from auth import check_auth, hash_key
        stored = hash_key("some-key")
        assert check_auth({}, stored) is False

    def test_get_actor_from_headers(self):
        """get_actor_from_headers should extract actor from X-Actor header."""
        from auth import get_actor_from_headers
        assert get_actor_from_headers({"x-actor": "cto"}) == "cto"
        assert get_actor_from_headers({}) == "owner"
        assert get_actor_from_headers({"x-actor": ""}) == "owner"
