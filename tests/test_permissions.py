"""Tests for AgentBoard permission system (key scoping)."""

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestPermissions:
    """Test permission decorator and helper functions in api/__init__.py."""

    def _make_headers(self, auth_valid=True, permissions="read,write"):
        return {
            "x-auth-valid": "true" if auth_valid else "false",
            "x-key-permissions": permissions,
            "x-key-id": "test-key-id",
        }

    def test_is_authenticated_true(self):
        from api import is_authenticated
        assert is_authenticated(self._make_headers()) is True

    def test_is_authenticated_false(self):
        from api import is_authenticated
        assert is_authenticated(self._make_headers(auth_valid=False)) is False

    def test_get_permissions(self):
        from api import get_permissions
        perms = get_permissions(self._make_headers(permissions="read,write,admin"))
        assert perms == ["read", "write", "admin"]

    def test_get_permissions_single(self):
        from api import get_permissions
        perms = get_permissions(self._make_headers(permissions="read"))
        assert perms == ["read"]

    def test_get_permissions_empty(self):
        from api import get_permissions
        perms = get_permissions(self._make_headers(permissions=""))
        assert perms == []

    def test_has_permission_read(self):
        from api import has_permission
        headers = self._make_headers(permissions="read,write")
        assert has_permission(headers, "read") is True
        assert has_permission(headers, "write") is True
        assert has_permission(headers, "admin") is False

    def test_has_permission_admin_includes_all(self):
        from api import has_permission
        headers = self._make_headers(permissions="admin")
        assert has_permission(headers, "read") is True
        assert has_permission(headers, "write") is True
        assert has_permission(headers, "admin") is True

    def test_has_permission_webhook(self):
        from api import has_permission
        headers = self._make_headers(permissions="read,webhook")
        assert has_permission(headers, "webhook") is True
        assert has_permission(headers, "write") is False

    def test_require_permission_granted(self):
        from api import require_permission

        @require_permission("write")
        def handler(params, query, body, headers):
            return 200, {"ok": True}

        result = handler({}, {}, b"", self._make_headers(permissions="read,write"))
        assert result == (200, {"ok": True})

    def test_require_permission_denied(self):
        from api import require_permission

        @require_permission("admin")
        def handler(params, query, body, headers):
            return 200, {"ok": True}

        result = handler({}, {}, b"", self._make_headers(permissions="read,write"))
        assert result[0] == 403
        assert result[1]["code"] == "FORBIDDEN"

    def test_require_permission_multiple(self):
        from api import require_permission

        @require_permission("write", "admin")
        def handler(params, query, body, headers):
            return 200, {"ok": True}

        # write only — should fail (needs both write AND admin)
        result = handler({}, {}, b"", self._make_headers(permissions="read,write"))
        assert result[0] == 403

        # write + admin — should pass
        result = handler({}, {}, b"", self._make_headers(permissions="read,write,admin"))
        assert result[0] == 200

    def test_require_permission_skip_unauthenticated(self):
        from api import require_permission

        @require_permission("admin")
        def handler(params, query, body, headers):
            return 200, {"ok": True}

        # Unauthenticated request — decorator should skip check
        # (server.py already blocks unauthenticated write requests)
        result = handler({}, {}, b"", self._make_headers(auth_valid=False))
        assert result[0] == 200


class TestAuthPermissions:
    """Test auth.py returning permissions from validate_key_against_db."""

    @classmethod
    def setup_class(cls):
        """Create in-memory DB with api_keys for testing."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("""CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT NOT NULL UNIQUE,
            label TEXT DEFAULT 'default',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_used_at TEXT,
            grace_until TEXT,
            agent TEXT DEFAULT '',
            permissions TEXT DEFAULT 'read,write',
            rate_limit INTEGER DEFAULT 60
        )""")
        conn.commit()

        # Insert test keys
        import hashlib
        cls.key_admin = "ab_test_admin_key_1234567890"
        cls.key_read = "ab_test_read_only_key_123456"
        cls.key_inactive = "ab_test_inactive_key_1234"

        conn.execute(
            "INSERT INTO api_keys (id, key_hash, label, is_active, permissions, agent) VALUES (?, ?, ?, ?, ?, ?)",
            ("admin-key", hashlib.sha256(cls.key_admin.encode()).hexdigest(), "admin-key", 1, "read,write,admin", "cto"),
        )
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, label, is_active, permissions, agent) VALUES (?, ?, ?, ?, ?, ?)",
            ("read-key", hashlib.sha256(cls.key_read.encode()).hexdigest(), "read-key", 1, "read", "viewer"),
        )
        conn.execute(
            "INSERT INTO api_keys (id, key_hash, label, is_active, permissions, agent) VALUES (?, ?, ?, ?, ?, ?)",
            ("inactive-key", hashlib.sha256(cls.key_inactive.encode()).hexdigest(), "inactive-key", 0, "read", "old"),
        )

        conn.commit()
        conn.close()

        # Monkey-patch get_db to return our test connection
        from db import get_db
        cls._original_get_db = get_db

        def mock_get_db():
            c = sqlite3.connect(":memory:")
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode = WAL")
            c.execute("""CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT NOT NULL UNIQUE,
                label TEXT DEFAULT 'default',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                last_used_at TEXT,
                grace_until TEXT,
                agent TEXT DEFAULT '',
                permissions TEXT DEFAULT 'read,write',
                rate_limit INTEGER DEFAULT 60
            )""")
            c.commit()
            import hashlib
            c.execute("INSERT INTO api_keys (id, key_hash, label, is_active, permissions, agent) VALUES (?, ?, ?, ?, ?, ?)",
                ("admin-key", hashlib.sha256("ab_test_admin_key_1234567890".encode()).hexdigest(), "admin-key", 1, "read,write,admin", "cto"))
            c.execute("INSERT INTO api_keys (id, key_hash, label, is_active, permissions, agent) VALUES (?, ?, ?, ?, ?, ?)",
                ("read-key", hashlib.sha256("ab_test_read_only_key_123456".encode()).hexdigest(), "read-key", 1, "read", "viewer"))
            c.commit()
            return c

        # Can't easily monkey-patch module-level get_db, so we test via auth module directly
        import auth
        cls._original_auth_get_db = auth.get_db
        auth.get_db = mock_get_db

    @classmethod
    def teardown_class(cls):
        import auth
        auth.get_db = cls._original_auth_get_db

    def test_validate_key_returns_permissions(self):
        from auth import validate_key_against_db
        valid, key_id, perms, agent, rl = validate_key_against_db("ab_test_admin_key_1234567890")
        assert valid is True
        assert key_id == "admin-key"
        assert "admin" in perms
        assert agent == "cto"

    def test_validate_key_read_only(self):
        from auth import validate_key_against_db
        valid, key_id, perms, agent, rl = validate_key_against_db("ab_test_read_only_key_123456")
        assert valid is True
        assert perms == "read"
        assert agent == "viewer"

    def test_validate_key_invalid(self):
        from auth import validate_key_against_db
        valid, key_id, perms, agent, rl = validate_key_against_db("ab_nonexistent_key")
        assert valid is False
        assert key_id is None
        assert perms == ""
        assert agent == ""

    def test_validate_key_inactive(self):
        from auth import validate_key_against_db
        # Inactive key without grace period should fail
        valid, _, _, _, _ = validate_key_against_db("ab_test_inactive_key_1234")
        assert valid is False


class TestAuthKeysCRUD:
    """Test auth_keys API with permissions support."""

    @classmethod
    def setup_class(cls):
        """Create in-memory DB for API key CRUD tests."""
        # Use a file-based temp DB to avoid shared in-memory DB issues
        import tempfile
        cls._db_path = os.path.join(tempfile.gettempdir(), f"test_auth_keys_crud_{id(cls)}.db")
        if os.path.exists(cls._db_path):
            os.unlink(cls._db_path)
        conn = sqlite3.connect(cls._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("""CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            key_hash TEXT NOT NULL UNIQUE,
            label TEXT DEFAULT 'default',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_used_at TEXT,
            grace_until TEXT,
            agent TEXT DEFAULT '',
            permissions TEXT DEFAULT 'read,write',
            rate_limit INTEGER DEFAULT 60
        )""")
        conn.commit()

        # Insert a seed admin key for auth
        import hashlib
        seed_hash = hashlib.sha256("ab_seed_admin_key".encode()).hexdigest()
        conn.execute("INSERT INTO api_keys (id, key_hash, label, is_active, permissions) VALUES (?, ?, ?, ?, ?)",
                     ("seed-admin", seed_hash, "seed", 1, "read,write,admin"))
        conn.commit()

        cls.conn = conn
        cls._db_path_for_mock = cls._db_path  # save for lambda
        import db
        cls._orig_get_db = db.get_db
        # Return a fresh connection each time since handlers call conn.close()
        db.get_db = lambda: sqlite3.connect(cls._db_path_for_mock)
        import auth
        cls._orig_auth_get_db = auth.get_db
        auth.get_db = lambda: sqlite3.connect(cls._db_path_for_mock)
        # Also patch api.auth_keys which already imported get_db at load time
        import api.auth_keys as _ak
        cls._orig_ak_get_db = _ak.get_db
        _ak.get_db = lambda: sqlite3.connect(cls._db_path_for_mock)

    @classmethod
    def teardown_class(cls):
        import db, auth, api.auth_keys as _ak
        db.get_db = cls._orig_get_db
        auth.get_db = cls._orig_auth_get_db
        _ak.get_db = cls._orig_ak_get_db
        cls.conn.close()
        if hasattr(cls, '_db_path') and os.path.exists(cls._db_path):
            os.unlink(cls._db_path)

    def test_create_key_with_permissions(self):
        from api.auth_keys import create_key
        headers = self._admin_headers()
        body = json.dumps({
            "label": "test-key",
            "permissions": "read",
            "agent": "pi",
            "rate_limit": 120,
        }).encode()
        status, data = create_key({}, {}, body, headers)
        assert status == 201
        assert data["permissions"] == "read"
        assert data["agent"] == "pi"
        assert data["rate_limit"] == 120
        assert "key" in data  # raw key returned

    def test_create_key_default_permissions(self):
        from api.auth_keys import create_key
        headers = self._admin_headers()
        body = json.dumps({"label": "default-perms"}).encode()
        status, data = create_key({}, {}, body, headers)
        assert status == 201
        assert data["permissions"] == "read,write"

    def test_create_key_invalid_permissions(self):
        from api.auth_keys import create_key
        headers = self._admin_headers()
        body = json.dumps({"label": "bad", "permissions": "read,superadmin"}).encode()
        status, data = create_key({}, {}, body, headers)
        assert status == 400
        assert "Invalid permissions" in data["error"]

    def _admin_headers(self):
        return {
            "x-auth-valid": "true",
            "x-key-permissions": "read,write,admin",
            "x-key-id": "seed-admin",
        }
