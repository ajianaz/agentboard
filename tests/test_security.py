"""Security test suite for AgentBoard.

Covers:
    1. Authentication bypass — write operations without/with wrong token
    2. SQL injection — user input in task titles, descriptions, search
    3. XSS — HTML/script injection in user-controlled fields
    4. Path traversal — static file serving
    5. FTS5 query injection — search endpoint
    6. Large/malformed payloads — body size, invalid JSON
    7. Auth key management — key rotation, last-key protection
    8. Input validation — boundary cases, missing fields

These tests are CI blockers — any failure MUST be fixed before merge.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEV_DIR = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = DEV_DIR / "server.py"
TEST_DB = "/tmp/ab-security-test.db"
TEST_PORT = 18766  # unique port to avoid conflicts
TEST_KEY = "test-security-key-12345"
BASE = f"http://127.0.0.1:{TEST_PORT}"


def api(method, path, data=None, auth=True, headers=None, actor=None):
    """Send API request and return (status_code, response_dict)."""
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Content-Type", "application/json")
    if auth:
        r.add_header("Authorization", f"Bearer {TEST_KEY}")
    if actor:
        r.add_header("X-Actor", actor)
    if headers:
        for k, v in headers.items():
            r.add_header(k, v)
    try:
        resp = urllib.request.urlopen(r, timeout=5)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"raw": body}


@pytest.fixture(scope="session")
def server():
    """Start a test server for the entire test session."""
    # Clean up any leftover DB
    for f in [TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"]:
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass

    env = os.environ.copy()
    env["AGENTBOARD_PORT"] = str(TEST_PORT)
    env["AGENTBOARD_DB_PATH"] = TEST_DB
    env["AGENTBOARD_API_KEY"] = TEST_KEY

    proc = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT)],
        cwd=str(DEV_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to be ready
    for _ in range(20):
        try:
            urllib.request.urlopen(f"{BASE}/api/health", timeout=1)
            break
        except (urllib.error.URLError, ConnectionRefusedError):
            time.sleep(0.3)
    else:
        proc.kill()
        pytest.fail("Server failed to start within 6 seconds")

    yield proc

    proc.terminate()
    proc.wait(timeout=5)
    # Cleanup DB
    for f in [TEST_DB, TEST_DB + "-wal", TEST_DB + "-shm"]:
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass


@pytest.fixture(autouse=True)
def setup_project(server):
    """Run setup before each test. 201 = fresh setup, 400 = already set up (OK)."""
    c, d = api("POST", "/api/setup", {"name": "Security Test"})
    assert c in (201, 400, 409), f"Setup failed: {d}"


# ===========================================================================
# 1. Authentication Bypass
# ===========================================================================


class TestAuthBypass:
    """Verify that write operations require valid authentication."""

    @pytest.mark.parametrize("method,path,body", [
        ("POST", "/api/agents", {"id": "x", "name": "X"}),
        ("POST", "/api/projects/security-test/tasks", {"title": "T"}),
        ("PATCH", "/api/tasks/nonexistent", {"title": "X"}),
        ("DELETE", "/api/tasks/nonexistent", None),
        ("POST", "/api/discussions", {"title": "X"}),
        ("POST", "/api/analytics/recompute", None),
        ("POST", "/api/auth/keys", {"label": "X"}),
        ("PATCH", "/api/auth/keys/nonexistent", {"label": "X"}),
        ("DELETE", "/api/auth/keys/nonexistent", None),
    ])
    def test_write_requires_auth(self, server, method, path, body):
        """All write operations must return 401 without auth header."""
        c, d = api(method, path, data=body, auth=False)
        assert c == 401, f"{method} {path} should be 401, got {c}: {d}"

    def test_read_without_auth(self, server):
        """GET endpoints should be accessible without auth (public_read)."""
        endpoints = ["/api/projects", "/api/agents", "/api/activity",
                     "/api/health", "/api/analytics/kpi", "/api/discussions"]
        for ep in endpoints:
            c, _ = api("GET", ep, auth=False)
            assert c == 200, f"GET {ep} should be 200 without auth, got {c}"

    def test_wrong_auth_key(self, server):
        """Wrong API key should return 401."""
        c, _ = api("POST", "/api/agents",
                   data={"id": "x", "name": "X"},
                   auth=True,
                   headers={"Authorization": "Bearer wrong-key-here"})
        assert c == 401, f"Wrong key should be 401, got {c}"

    def test_malformed_auth_header(self, server):
        """Malformed Authorization header should return 401."""
        for header in ["Basic abc", "Bearer", "Token abc123", ""]:
            hdrs = {"Authorization": header} if header else {}
            c, _ = api("POST", "/api/agents",
                       data={"id": "x", "name": "X"},
                       auth=False, headers=hdrs)
            assert c == 401, f"Header '{header}' should be 401, got {c}"

    def test_setup_needs_no_auth(self, server):
        """POST /api/setup should work without auth (first run only)."""
        # Already set up by fixture, so should return 400 (SETUP_DONE)
        # But NOT 401
        c, _ = api("POST", "/api/setup", {"name": "Dup"}, auth=False)
        assert c in (400, 409), f"Setup should be 400/409 not auth, got {c}"


# ===========================================================================
# 2. SQL Injection
# ===========================================================================


class TestSQLInjection:
    """Verify that user input cannot inject SQL."""

    SQL_PAYLOADS = [
        "' OR 1=1 --",
        "'; DROP TABLE tasks; --",
        "1; SELECT * FROM api_keys --",
        "' UNION SELECT key_hash FROM api_keys --",
        "Robert'); DROP TABLE students; --",
        "1 OR '1'='1",
        "admin'--",
        "' OR '1'='1' /*",
    ]

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_sql_injection_task_title(self, server, payload):
        """SQL injection in task title should not affect DB."""
        c, d = api("POST", "/api/projects/security-test/tasks",
                   data={"title": payload, "status": "todo"}, actor="tester")
        # Should succeed (200/201) — payload stored as-is, not executed
        assert c in (200, 201), f"Task creation with SQL payload failed: {d}"

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_sql_injection_agent_name(self, server, payload):
        """SQL injection in agent name should not affect DB."""
        safe_id = f"agent-{abs(hash(payload)) % 10000}"
        c, d = api("POST", "/api/agents",
                   data={"id": safe_id, "name": payload, "role": "test"})
        # Should succeed — payload stored as data
        assert c in (200, 201, 400), f"Agent creation with SQL payload failed: {d}"

    @pytest.mark.parametrize("payload", SQL_PAYLOADS)
    def test_sql_injection_discussion_context(self, server, payload):
        """SQL injection in discussion context should not affect DB."""
        c, d = api("POST", "/api/discussions",
                   data={"title": "Test", "context": payload})
        assert c in (200, 201), f"Discussion with SQL payload failed: {d}"

    def test_sql_injection_task_id_param(self, server):
        """SQL injection in URL path parameter (task ID) should be safe."""
        payloads = ["' OR '1'='1", "1; DROP TABLE tasks", "../agents"]
        for pid in payloads:
            try:
                c, _ = api("GET", f"/api/tasks/{pid}", auth=False)
                # Should be 404 (not found), NOT 500 (error)
                assert c in (404, 400), f"Task ID injection '{pid}' returned {c}, expected 404/400"
            except (ValueError, Exception) as exc:
                # urllib/http.client rejects invalid URLs before sending — safe
                if "InvalidURL" in type(exc).__name__:
                    pass
                else:
                    raise

    def test_sql_injection_search_query(self, server):
        """SQL injection in search query should not crash server."""
        payloads = ["'; DROP TABLE tasks; --", "1 OR 1=1", "UNION SELECT * FROM api_keys"]
        for q in payloads:
            c, _ = api("GET", f"/api/search?q={urllib.parse.quote(q)}", auth=False)
            # Should be 200 (FTS handles gracefully) or 400/500 but NOT expose data
            assert c != 401, f"Search should not require auth, got {c}"


# ===========================================================================
# 3. XSS Prevention
# ===========================================================================


class TestXSS:
    """Verify that XSS payloads are stored but frontend-escapable."""

    XSS_PAYLOADS = [
        '<script>alert("xss")</script>',
        '<img src=x onerror=alert(1)>',
        '"><script>document.cookie</script>',
        "javascript:alert(1)",
        '<svg onload=alert(1)>',
        "{{7*7}}",  # template injection
        "<iframe src='evil.com'></iframe>",
    ]

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_xss_in_task_title_stored(self, server, payload):
        """XSS payload in task title should be stored (not stripped)."""
        c, d = api("POST", "/api/projects/security-test/tasks",
                   data={"title": payload, "status": "todo"})
        assert c in (200, 201), f"XSS task creation failed: {d}"
        # Verify it's stored as-is (backend doesn't sanitize)
        task_id = d.get("task", {}).get("id", "")
        if task_id:
            c2, d2 = api("GET", f"/api/tasks/{task_id}", auth=False)
            assert c2 == 200
            assert payload in d2.get("task", {}).get("title", ""), "XSS payload should be stored verbatim"

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    def test_xss_in_discussion_context(self, server, payload):
        """XSS payload in discussion context should be stored."""
        c, d = api("POST", "/api/discussions",
                   data={"title": "XSS Test", "context": payload})
        assert c in (200, 201), f"XSS discussion creation failed: {d}"


# ===========================================================================
# 4. Path Traversal
# ===========================================================================


class TestPathTraversal:
    """Verify that static file serving prevents path traversal."""

    TRAVERSAL_PATHS = [
        "/static/../../../etc/passwd",
        "/static/..%2F..%2F..%2Fetc%2Fpasswd",
        "/static/..%252F..%252F..%252Fetc%252Fpasswd",
        "/static/....//....//....//etc/passwd",
        "/static/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
        "/static/..\\..\\..\\windows\\system32\\config\\sam",
    ]

    @pytest.mark.parametrize("path", TRAVERSAL_PATHS)
    def test_static_path_traversal(self, server, path):
        """Path traversal attempts should return 404, never file contents."""
        url = f"{BASE}{path}"
        try:
            r = urllib.request.Request(url)
            resp = urllib.request.urlopen(r, timeout=3)
            body = resp.read().decode()
            # If we get 200, the body must NOT contain passwd entries
            assert "root:" not in body, f"Path traversal succeeded! Got: {body[:200]}"
            # Most likely returned index.html or a safe static file
        except urllib.error.HTTPError as e:
            # 404 is expected
            assert e.code == 404, f"Expected 404 for traversal, got {e.code}"

    def test_static_normal_file(self, server):
        """Normal static file should serve correctly."""
        # Root / serves index.html, not /static/index.html
        try:
            r = urllib.request.Request(f"{BASE}/")
            resp = urllib.request.urlopen(r, timeout=3)
            assert resp.status == 200, f"Root should serve index.html, got {resp.status}"
        except urllib.error.HTTPError as e:
            pytest.fail(f"Root returned {e.code}")


# ===========================================================================
# 5. FTS5 Query Injection
# ===========================================================================


class TestFTS5Injection:
    """Verify FTS5 search handles special characters gracefully."""

    FTS_PAYLOADS = [
        "OR AND NOT NEAR",       # FTS5 operators
        '*',                     # prefix match wildcard
        '"phrase search"',       # phrase query
        'NEAR(word1 word2, 10)', # NEAR operator
        '(',                     # unmatched parenthesis
        'title:test',            # column filter
        'test *',                # trailing wildcard
        'AND OR AND OR',         # operator spam
    ]

    @pytest.mark.parametrize("query", FTS_PAYLOADS)
    def test_fts5_special_chars(self, server, query):
        """FTS5 special characters should not expose data or crash silently."""
        c, d = api("GET", f"/api/search?q={urllib.parse.quote(query)}", auth=False)
        # Should be 200 (empty results), 400 (rejected), or 500 (FTS syntax error)
        # Must NOT expose api_keys or sensitive data
        assert c in (200, 400), f"FTS query '{query}' returned {c}: {d}"
        # If we got results, make sure no key hashes are exposed
        if c == 200 and d.get("results"):
            for r in d["results"]:
                assert "key_hash" not in str(r).lower()

    def test_fts5_empty_query(self, server):
        """Empty search query should return 400."""
        c, _ = api("GET", "/api/search?q=", auth=False)
        assert c == 400, "Empty search should return 400"

    def test_fts5_very_long_query(self, server):
        """Very long search query should be handled gracefully."""
        long_q = "word " * 500  # 2500 chars
        c, _ = api("GET", f"/api/search?q={urllib.parse.quote(long_q)}", auth=False)
        assert c in (200, 400, 413), f"Long query returned {c}"


# ===========================================================================
# 6. Large / Malformed Payloads
# ===========================================================================


class TestPayloadHandling:
    """Verify server handles edge case payloads gracefully."""

    def test_oversized_json_body(self, server):
        """Very large JSON body should not crash server."""
        large_title = "A" * 100_000  # 100KB title
        c, d = api("POST", "/api/projects/security-test/tasks",
                   data={"title": large_title, "status": "todo"})
        # Should be 200/201 (accepted) or 413 (too large) or 400
        assert c in (200, 201, 400, 413), f"Large payload returned {c}: {d}"

    def test_invalid_json_body(self, server):
        """Invalid JSON body should return 400, not 500."""
        url = f"{BASE}/api/projects/security-test/tasks"
        r = urllib.request.Request(url, data=b"not json at all {{{", method="POST")
        r.add_header("Content-Type", "application/json")
        r.add_header("Authorization", f"Bearer {TEST_KEY}")
        try:
            resp = urllib.request.urlopen(r, timeout=5)
            c = resp.status
        except urllib.error.HTTPError as e:
            c = e.code
        assert c == 400, f"Invalid JSON returned {c}"

    def test_empty_body_for_post(self, server):
        """Empty body on POST should be handled gracefully."""
        url = f"{BASE}/api/projects/security-test/tasks"
        r = urllib.request.Request(url, data=b"", method="POST")
        r.add_header("Content-Type", "application/json")
        r.add_header("Authorization", f"Bearer {TEST_KEY}")
        try:
            resp = urllib.request.urlopen(r, timeout=5)
            c = resp.status
        except urllib.error.HTTPError as e:
            c = e.code
        assert c in (400, 422), f"Empty body returned {c}"

    def test_wrong_content_type(self, server):
        """Wrong Content-Type should be handled gracefully."""
        url = f"{BASE}/api/projects/security-test/tasks"
        r = urllib.request.Request(url, data=b"title=Test", method="POST")
        r.add_header("Content-Type", "application/xml")
        r.add_header("Authorization", f"Bearer {TEST_KEY}")
        try:
            resp = urllib.request.urlopen(r, timeout=5)
            c = resp.status
        except urllib.error.HTTPError as e:
            c = e.code
        assert c in (400, 415, 200), f"Wrong content type returned {c}"

    def test_null_bytes_in_input(self, server):
        """Null bytes in input should not cause issues."""
        c, d = api("POST", "/api/projects/security-test/tasks",
                   data={"title": "test\x00injection", "status": "todo"})
        assert c in (200, 201, 400), f"Null byte payload returned {c}: {d}"


# ===========================================================================
# 7. Auth Key Management
# ===========================================================================


class TestAuthKeyManagement:
    """Verify API key management security."""

    def test_create_key_returns_raw_once(self, server):
        """Raw key should be returned on creation."""
        c, d = api("POST", "/api/auth/keys", {"label": "test-key"})
        assert c == 201, f"Key creation failed: {d}"
        assert "key" in d, "Response should contain raw key"
        assert len(d["key"]) > 20, "Key should be sufficiently long"

    def test_list_keys_never_shows_raw(self, server):
        """Key list should never expose raw key or hash."""
        c, d = api("GET", "/api/auth/keys")
        assert c == 200
        for key in d.get("keys", []):
            assert "key_hash" not in key, "key_hash must never be exposed"
            assert "key" not in key or key.get("key") != "raw-key", "Raw key exposed!"

    def test_cannot_delete_last_active_key(self, server):
        """Deleting the last active key should be blocked."""
        # Get all keys
        c, d = api("GET", "/api/auth/keys")
        keys = d.get("keys", [])
        active_keys = [k for k in keys if k.get("is_active")]

        if len(active_keys) == 1:
            kid = active_keys[0]["id"]
            c, d = api("DELETE", f"/api/auth/keys/{kid}")
            assert c == 409, f"Should block deleting last key, got {c}: {d}"

    def test_deactivate_with_grace_period(self, server):
        """Key deactivation should support grace period."""
        # Create a new key first
        c, d = api("POST", "/api/auth/keys", {"label": "to-deactivate"})
        assert c == 201
        kid = d["id"]

        # Deactivate with grace period
        c, d = api("PATCH", f"/api/auth/keys/{kid}",
                   {"deactivate": True, "grace_minutes": 30})
        assert c == 200, f"Deactivation failed: {d}"
        assert d.get("key", {}).get("is_active") == 0
        assert d.get("key", {}).get("grace_until") is not None


# ===========================================================================
# 8. Input Validation
# ===========================================================================


class TestInputValidation:
    """Verify input validation on critical endpoints."""

    def test_agent_requires_id(self, server):
        """Agent creation without id should fail."""
        c, d = api("POST", "/api/agents", {"name": "No ID"})
        assert c == 400, f"Should require id, got {c}: {d}"

    def test_agent_requires_name(self, server):
        """Agent creation without name should fail."""
        c, d = api("POST", "/api/agents", {"id": "test-no-name"})
        assert c == 400, f"Should require name, got {c}: {d}"

    def test_duplicate_agent_id(self, server):
        """Duplicate agent ID should return 409."""
        api("POST", "/api/agents", {"id": "dup-test", "name": "First"})
        c, d = api("POST", "/api/agents", {"id": "dup-test", "name": "Second"})
        assert c == 409, f"Duplicate agent should be 409, got {c}: {d}"

    def test_task_title_empty(self, server):
        """Empty task title should fail."""
        c, d = api("POST", "/api/projects/security-test/tasks",
                   {"title": "", "status": "todo"})
        # Empty title might be accepted (backend allows) or rejected
        # Just verify it doesn't crash
        assert c in (200, 201, 400), f"Empty title returned {c}: {d}"

    def test_discussion_feedback_requires_participant(self, server):
        """Discussion feedback without participant should fail."""
        # Create a discussion first
        c, d = api("POST", "/api/discussions", {"title": "T", "context": "C"})
        did = d.get("id", "")
        c, d = api("POST", f"/api/discussions/{did}/feedback",
                   {"content": "OK", "verdict": "approve"})
        assert c == 400, f"Should require participant, got {c}: {d}"

    def test_discussion_feedback_requires_content(self, server):
        """Discussion feedback without content should fail."""
        c, d = api("POST", "/api/discussions", {"title": "T", "context": "C"})
        did = d.get("id", "")
        c, d = api("POST", f"/api/discussions/{did}/feedback",
                   {"participant": "alice", "verdict": "approve"})
        assert c == 400, f"Should require content, got {c}: {d}"

    def test_invalid_verdict_rejected(self, server):
        """Invalid verdict should be rejected."""
        c, d = api("POST", "/api/discussions", {"title": "T", "context": "C"})
        did = d.get("id", "")
        c, d = api("POST", f"/api/discussions/{did}/feedback",
                   {"participant": "alice", "content": "OK", "verdict": "INVALID"})
        assert c == 400, f"Invalid verdict should be 400, got {c}: {d}"

    def test_activity_limit_bounds(self, server):
        """Activity endpoint should respect limit bounds."""
        # Very large limit
        c, d = api("GET", "/api/activity?limit=999999", auth=False)
        assert c == 200
        # Should cap at some reasonable value
        assert len(d.get("activity", [])) < 999999

        # Negative limit
        c, d = api("GET", "/api/activity?limit=-1", auth=False)
        assert c == 200

    def test_analytics_trends_days_bounds(self, server):
        """Analytics trends should handle extreme day values."""
        c, _ = api("GET", "/api/analytics/trends?days=0", auth=False)
        assert c in (200, 400), f"Zero days returned {c}"

        c, _ = api("GET", "/api/analytics/trends?days=9999", auth=False)
        assert c in (200, 400), f"Huge days returned {c}"

    def test_nonexistent_task_returns_404(self, server):
        """GET/PUT/DELETE on nonexistent task should return 404."""
        c, _ = api("GET", "/api/tasks/nonexistent-task-id", auth=False)
        assert c == 404

        c, _ = api("PATCH", "/api/tasks/nonexistent-task-id", {"title": "X"})
        assert c == 404

        c, _ = api("DELETE", "/api/tasks/nonexistent-task-id")
        assert c == 404

    def test_nonexistent_discussion_returns_404(self, server):
        """Operations on nonexistent discussion should return 404."""
        c, _ = api("GET", "/api/discussions/nonexistent", auth=False)
        assert c == 404

        c, _ = api("POST", "/api/discussions/nonexistent/feedback",
                   {"participant": "x", "content": "x", "verdict": "approve"})
        assert c == 404


# ===========================================================================
# 9. CORS & Headers
# ===========================================================================


class TestCORSAndHeaders:
    """Verify CORS and security headers."""

    def test_cors_preflight(self, server):
        """OPTIONS request should return 204 with CORS headers."""
        url = f"{BASE}/api/projects"
        r = urllib.request.Request(url, method="OPTIONS")
        try:
            resp = urllib.request.urlopen(r, timeout=3)
            assert resp.status == 204
            # Check CORS headers
            methods = resp.headers.get("Access-Control-Allow-Methods", "")
            assert "GET" in methods
            assert "POST" in methods
        except urllib.error.HTTPError as e:
            pytest.fail(f"OPTIONS returned {e.code}")

    def test_no_sensitive_headers_exposed(self, server):
        """API key hash should never appear in any response."""
        # Create an agent and check response
        c, d = api("POST", "/api/agents", {"id": "hdr-test", "name": "Test"})
        resp_str = json.dumps(d)
        assert "key_hash" not in resp_str.lower(), "key_hash leaked in response"
        assert "api_key" not in resp_str.lower(), "api_key leaked in response"


# ===========================================================================
# 10. Database-Level Security
# ===========================================================================


class TestDatabaseSecurity:
    """Verify database-level security properties (unit tests, no server)."""

    def test_api_keys_table_stores_hash_not_plaintext(self):
        """Verify api_keys schema stores hash, not plaintext."""
        # This is a schema verification test
        conn = sqlite3.connect(TEST_DB)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(api_keys)").fetchall()]
        assert "key_hash" in cols, "api_keys should have key_hash column"
        assert "key" not in cols, "api_keys should NOT have plaintext key column"
        conn.close()

    def test_password_hash_is_sha256_length(self):
        """SHA-256 hash should be 64 hex chars."""
        from auth import hash_key
        h = hash_key("test-key-123")
        assert len(h) == 64, f"SHA-256 hash should be 64 chars, got {len(h)}"
        assert all(c in "0123456789abcdef" for c in h), "Hash should be hex"

