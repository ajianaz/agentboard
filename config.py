"""config.py — Configuration loader for AgentBoard.

Loads settings from agentboard.toml using stdlib tomllib (Python 3.11+).
Config is fully optional — if no file exists, sensible defaults are used.

Priority hierarchy (highest wins):
    1. CLI arguments (--port, --host, --config)
    2. Environment variables (AGENTBOARD_PORT, AGENTBOARD_HOST, AGENTBOARD_CONFIG)
    3. agentboard.toml file (project root or AGENTBOARD_CONFIG path)
    4. Built-in defaults

Usage:
    from config import load_config, get_config
    cfg = get_config()  # lazy-loaded singleton
    print(cfg["server"]["port"])
"""

import argparse
import copy
import os
import sys
import tomllib
from pathlib import Path

# ── Constants ──────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

DEFAULTS = {
    "server": {
        "host": "0.0.0.0",
        "port": 8765,
        "cors_origins": ["*"],
        "proxy_prefix": "",
        "log_requests": False,
        "maintenance": False,
    },
    "database": {
        "path": "agentboard.db",
    },
    "auth": {
        "api_key_file": ".api_key",
        "public_read": True,
        "public_get_routes": [
            "/api/health",
            "/api/projects",
            "/api/tasks",
            "/api/pages",
            "/api/stats",
            "/api/stats/public",
            "/api/search",
            "/api/discussions",
        ],
    },
    "features": {
        "export_enabled": True,
        "import_enabled": True,
    },
    "webhooks": {
        "enabled": False,
        "timeout": 5,
        "agent_ports": {},
    },
    "analytics": {
        "interval_seconds": 300,
        "retention_daily_kpi": 90,
        "retention_weekly_kpi": 365,
        "retention_activity": 180,
    },
    "feedback_watcher": {
        "enabled": False,
        "directory": "",  # absolute path, or relative to BASE_DIR; empty = disabled
        "poll_interval": 5,
    },
}

# Singleton — loaded once on first access
_config = None


# ── Deep merge ─────────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values win."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ── Path resolution ───────────────────────────────────────────────────

def _resolve_path(value: str) -> Path:
    """Resolve a path: absolute stays absolute, relative is based on BASE_DIR."""
    p = Path(value)
    if p.is_absolute():
        return p
    return BASE_DIR / p


# ── Config loading ────────────────────────────────────────────────────

def _find_config_file(cli_path: str | None = None) -> Path | None:
    """Find the TOML config file.

    Search order:
        1. CLI --config argument
        2. AGENTBOARD_CONFIG environment variable
        3. agentboard.toml in project root (next to server.py)
    """
    # CLI flag takes priority
    if cli_path:
        p = Path(cli_path)
        if p.exists():
            return p
        print(f"[AgentBoard] Warning: config file not found: {cli_path}", file=sys.stderr)

    # Environment variable
    env_path = os.environ.get("AGENTBOARD_CONFIG")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        print(f"[AgentBoard] Warning: AGENTBOARD_CONFIG={env_path} not found", file=sys.stderr)

    # Default location
    default = BASE_DIR / "agentboard.toml"
    if default.exists():
        return default

    return None


def load_config(cli_args: list | None = None) -> dict:
    """Load configuration with full priority hierarchy.

    Args:
        cli_args: Optional list of CLI arguments (for testing). Defaults to sys.argv.

    Returns:
        Fully resolved configuration dictionary.
    """
    # 1. Start with built-in defaults
    config = copy.deepcopy(DEFAULTS)

    # 2. Parse CLI arguments (for --config, --port, --host)
    parser = argparse.ArgumentParser(
        prog="agentboard",
        description="AgentBoard — Standalone project board for human+AI collaboration",
        add_help=False,
    )
    parser.add_argument("--config", "-c", help="Path to agentboard.toml")
    parser.add_argument("--port", "-p", type=int, help="Server port")
    parser.add_argument("--host", help="Server bind address")
    parser.add_argument("--log", action="store_true", help="Enable request logging")
    parsed, _ = parser.parse_known_args(cli_args)

    # 3. Load TOML file
    config_file = _find_config_file(parsed.config)
    if config_file:
        with open(config_file, "rb") as f:
            file_config = tomllib.load(f)
        config = _deep_merge(config, file_config)

    # 4. Environment variable overrides
    if os.environ.get("AGENTBOARD_PORT"):
        config["server"]["port"] = int(os.environ["AGENTBOARD_PORT"])
    if os.environ.get("AGENTBOARD_HOST"):
        config["server"]["host"] = os.environ["AGENTBOARD_HOST"]
    if os.environ.get("AGENTBOARD_DB_PATH"):
        config["database"]["path"] = os.environ["AGENTBOARD_DB_PATH"]
    if os.environ.get("AGENTBOARD_API_KEY_FILE"):
        config["auth"]["api_key_file"] = os.environ["AGENTBOARD_API_KEY_FILE"]
    if os.environ.get("AGENTBOARD_PUBLIC_READ"):
        config["auth"]["public_read"] = os.environ["AGENTBOARD_PUBLIC_READ"].lower() in ("true", "1", "yes")
    if os.environ.get("AGENTBOARD_PUBLIC_ROUTES"):
        config["auth"]["public_get_routes"] = [
            r.strip() for r in os.environ["AGENTBOARD_PUBLIC_ROUTES"].split(",") if r.strip()
        ]
    if os.environ.get("AGENTBOARD_MAINTENANCE"):
        config["server"]["maintenance"] = os.environ["AGENTBOARD_MAINTENANCE"].lower() in ("true", "1", "yes")

    # 5. CLI argument overrides (highest priority)
    if parsed.port is not None:
        config["server"]["port"] = parsed.port
    if parsed.host is not None:
        config["server"]["host"] = parsed.host
    if parsed.log:
        config["server"]["log_requests"] = True

    # 6. Resolve relative paths to BASE_DIR
    config["database"]["path"] = _resolve_path(config["database"]["path"])
    config["auth"]["api_key_file"] = _resolve_path(config["auth"]["api_key_file"])

    return config


def get_config() -> dict:
    """Get the lazy-loaded config singleton.

    Loads on first access. Subsequent calls return the cached instance.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> dict:
    """Force reload configuration (e.g., after CLI test setup)."""
    global _config
    _config = load_config()
    return _config
