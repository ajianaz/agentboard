"""auth.py - API key management, validation, and request auth for AgentBoard.

Supports multi-key management with rotation and grace period.
Keys are stored hashed in the `api_keys` table (schema v3).
Legacy single-key mode (.api_key file) is auto-imported on first migration.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# API_KEY_FILE resolved by config module at runtime
from config import get_config
from db import get_db, gen_id

SESSION_COOKIE = "agentboard_session"
_GRACE_MINUTES = 5


def generate_api_key() -> str:
    """Generate a new random API key with 'ab_' prefix."""
    return "ab_" + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    """Hash an API key for storage (never store raw keys)."""
    return hashlib.sha256(key.encode()).hexdigest()


def get_or_create_api_key() -> str:
    """Load existing API key from file or env, or generate and save a new one.

    This is the legacy single-key path. Used for backward compatibility
    and initial setup. Once the api_keys table exists, prefer key_manager.
    """
    env_key = os.environ.get("AGENTBOARD_API_KEY")
    if env_key:
        return env_key
    cfg = get_config()
    key_file = cfg["auth"]["api_key_file"]
    if key_file.exists():
        return key_file.read_text().strip()
    key = generate_api_key()
    fd = os.open(str(key_file), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key.encode())
    finally:
        os.close(fd)
    return key


def _ensure_db_key():
    """Ensure at least one active key exists in the api_keys table.

    On first run (migration), imports the legacy .api_key file.
    On fresh install, generates a new key.
    Returns the raw key (only shown once during creation).
    """
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM api_keys WHERE is_active = 1 LIMIT 1"
    ).fetchone()

    if row:
        conn.close()
        return None  # keys already exist, no new key to return

    # No active keys — try to import legacy key
    import traceback
    try:
        legacy_key = get_or_create_api_key()
        key_hash = hash_key(legacy_key)
        kid = gen_id()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """INSERT INTO api_keys (id, key_hash, label, is_active, created_at)
               VALUES (?, ?, ?, 1, ?)""",
            (kid, key_hash, "imported", now),
        )
        conn.commit()
        conn.close()
        return None  # imported, no new key shown
    except (sqlite3.IntegrityError, OSError) as e:
        sys.stderr.write(f"[AgentBoard] Legacy key import failed: {e}\n")
        traceback.print_exc(file=sys.stderr)
        # Don't fall through — re-raise so caller knows something is wrong
        raise

    # Fresh install — generate new key
    raw_key = generate_api_key()
    key_hash = hash_key(raw_key)
    kid = gen_id()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        """INSERT INTO api_keys (id, key_hash, label, is_active, created_at)
           VALUES (?, ?, ?, 1, ?)""",
        (kid, key_hash, "default", now),
    )
    conn.commit()
    conn.close()
    return raw_key  # return raw key so it can be displayed to user


def validate_key_against_db(raw_key: str) -> tuple:
    """Check a raw key against all active keys in the database.

    Supports grace period — keys recently deactivated still work
    until their grace_until timestamp passes.

    Returns:
        (is_valid: bool, key_id: str|None)
    """
    key_hash = hash_key(raw_key)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = get_db()

    # Check active keys
    row = conn.execute(
        """SELECT id FROM api_keys
           WHERE key_hash = ? AND is_active = 1""",
        (key_hash,),
    ).fetchone()

    if row:
        # Update last_used_at
        conn.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
            (now, row["id"]),
        )
        conn.commit()
        conn.close()
        return True, row["id"]

    # Check grace period keys
    row = conn.execute(
        """SELECT id FROM api_keys
           WHERE key_hash = ? AND is_active = 0
           AND grace_until IS NOT NULL AND grace_until > ?""",
        (key_hash, now),
    ).fetchone()

    conn.close()
    if row:
        return True, row["id"]

    return False, None


def validate_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a raw key against a stored hash.

    Legacy single-key validation (for .api_key file mode).
    """
    return hmac.compare_digest(hash_key(raw_key), stored_hash)


def check_auth(headers: dict, stored_hash: str) -> bool:
    """Check auth using the legacy single-key path.

    Used as fallback when api_keys table doesn't exist yet.
    """
    if not stored_hash:
        # Defensive: reject if no key configured, even if currently unreachable
        # (hash_key() always returns non-empty, but protect against future misuse)
        return False
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if len(token) > 1024:
            return False
        return validate_key(token, stored_hash)
    return False


def check_auth_multi(headers: dict) -> tuple:
    """Check auth using the multi-key database path.

    Returns:
        (is_valid: bool, key_id: str|None)
    """
    auth_header = headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return False, None
    token = auth_header[7:]
    if len(token) > 1024:
        return False, None
    return validate_key_against_db(token)


def has_db_keys() -> bool:
    """Check if the api_keys table has any ACTIVE keys."""
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as c FROM api_keys WHERE is_active = 1").fetchone()
    conn.close()
    return row["c"] > 0


def get_actor_from_headers(headers: dict) -> str:
    """Determine who is making the request from the X-Actor header."""
    import re
    actor = headers.get("x-actor", "")
    if not actor:
        return "owner"
    # Sanitize: alphanumeric, underscore, hyphen only, max 64 chars
    actor = re.sub(r"[^a-zA-Z0-9_-]", "", actor)[:64]
    return actor if actor else "owner"
