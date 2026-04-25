"""auth.py - API key generation, validation, and request auth for AgentBoard."""

import hashlib
import hmac
import os
import secrets
from pathlib import Path

# API_KEY_FILE resolved by config module at runtime
from config import get_config

API_KEY_FILE = None  # set on first use
SESSION_COOKIE = "agentboard_session"


def generate_api_key() -> str:
    """Generate a new random API key with 'ab_' prefix."""
    return f"ab_{secrets.token_urlsafe(32)}"


def hash_key(key: str) -> str:
    """Hash an API key for storage (never store raw keys)."""
    return hashlib.sha256(key.encode()).hexdigest()


def get_or_create_api_key() -> str:
    """Load existing API key from file or env, or generate and save a new one.

    Priority:
        1. AGENTBOARD_API_KEY environment variable (highest)
        2. Existing API key file
        3. Generate new key and save to file

    The API key file is created with 0o600 permissions (owner read/write only).
    """
    global API_KEY_FILE
    # 1. Environment variable override (for Docker / CI)
    env_key = os.environ.get("AGENTBOARD_API_KEY")
    if env_key:
        return env_key

    # 2. Load from file
    if API_KEY_FILE is None:
        API_KEY_FILE = get_config()["auth"]["api_key_file"]
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()

    # 3. Generate and save
    key = generate_api_key()
    API_KEY_FILE.write_text(key)
    API_KEY_FILE.chmod(0o600)
    return key


def validate_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a raw key against a stored hash."""
    return hmac.compare_digest(hash_key(raw_key), stored_hash)


def check_auth(headers: dict, stored_hash: str) -> bool:
    """Extract Bearer token from the Authorization header and validate it.

    Returns True if no stored_hash is configured (first-run setup mode).
    """
    if not stored_hash:
        return True
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return validate_key(token, stored_hash)
    return False


def get_actor_from_headers(headers: dict) -> str:
    """Determine who is making the request from the X-Actor header.

    Defaults to 'owner' if no X-Actor header is present.
    """
    actor = headers.get("x-actor", "")
    return actor if actor else "owner"
