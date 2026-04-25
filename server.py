#!/usr/bin/env python3
"""AgentBoard — Standalone multi-project task board for human+AI collaboration.

Main entry point. Starts an HTTP server that serves the SPA frontend,
static assets, and REST API endpoints using only Python 3.13 stdlib.

Usage:
    python server.py
    AGENTBOARD_PORT=9000 python server.py
    AGENTBOARD_HOST=127.0.0.1 python server.py
"""

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Local imports
from db import get_db
from auth import get_or_create_api_key, hash_key, check_auth

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_PORT = 8765

# Lazy-loaded API router (may not exist yet during early development)
_api_router = None
_api_router_error = None


def _get_api_router():
    """Lazily import the API router, caching the result or error."""
    global _api_router, _api_router_error
    if _api_router is not None:
        return _api_router
    if _api_router_error is not None:
        raise _api_router_error
    try:
        from api import router
        _api_router = router
        return _api_router
    except ImportError as e:
        _api_router_error = e
        raise


class RequestHandler(BaseHTTPRequestHandler):
    """Main request handler with URL routing, auth, CORS, and static file serving."""

    # ── HTTP method dispatchers ──────────────────────────────────────────

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_PATCH(self):
        self._route("PATCH")

    def do_DELETE(self):
        self._route("DELETE")

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self._send_cors_headers()
        self.send_response(204)
        self.end_headers()

    # ── Core routing ─────────────────────────────────────────────────────

    def _route(self, method: str):
        """Parse the request URL, check auth, and dispatch to the appropriate handler."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        # Serve static files and root without auth
        if path == "" or path == "/":
            self._serve_file(STATIC_DIR / "index.html", "text/html")
            return

        if path.startswith("/static/"):
            relative = path[len("/static/"):]
            filepath = STATIC_DIR / relative
            self._serve_file(filepath, self._guess_content_type(path))
            return

        # Auth check for all other routes
        # Skip auth for /api/setup to allow first-run configuration
        if path != "/api/setup":
            api_key_hash = hash_key(get_or_create_api_key())
            if not check_auth(self.headers, api_key_hash):
                self._json_response(
                    {"error": "Unauthorized", "code": "UNAUTHORIZED"}, 401
                )
                return

        # API routes
        self._handle_api(method, path, query)

    # ── API handler ──────────────────────────────────────────────────────

    def _handle_api(self, method: str, path: str, query: dict):
        """Route API requests to the API router module.

        If the API module is not yet implemented, returns 501 NOT_IMPLEMENTED.
        """
        body = self._read_body()

        try:
            router = _get_api_router()
        except ImportError:
            self._json_response(
                {"error": "API not implemented", "code": "NOT_IMPLEMENTED"}, 501
            )
            return

        try:
            result = router.handle(method, path, query, body, self.headers)
        except Exception as exc:
            # Catch-all for unhandled API errors
            self._json_response(
                {"error": "Internal server error", "code": "INTERNAL_ERROR",
                 "detail": str(exc)},
                500,
            )
            return

        if result is None:
            self._json_response(
                {"error": "Not found", "code": "NOT_FOUND"}, 404
            )
        else:
            status, data = result
            self._json_response(data, status)

    # ── Request body reading ─────────────────────────────────────────────

    def _read_body(self) -> bytes:
        """Read the request body based on Content-Length header."""
        length = int(self.headers.get("content-length", 0))
        return self.rfile.read(length) if length > 0 else b""

    # ── Response helpers ─────────────────────────────────────────────────

    def _json_response(self, data, status: int = 200):
        """Send a JSON response with CORS headers."""
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _serve_file(self, filepath: Path, content_type: str):
        """Serve a static file with path security (must be under STATIC_DIR)."""
        # Security: ensure the resolved path is within STATIC_DIR
        try:
            filepath.resolve().relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._json_response({"error": "Not found", "code": "NOT_FOUND"}, 404)
            return

        if not filepath.exists() or not filepath.is_file():
            self._json_response({"error": "Not found", "code": "NOT_FOUND"}, 404)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(filepath.read_bytes())

    # ── CORS ─────────────────────────────────────────────────────────────

    def _send_cors_headers(self):
        """Send permissive CORS headers for cross-origin API access."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, PATCH, DELETE, OPTIONS",
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-Actor",
        )

    # ── MIME type mapping ────────────────────────────────────────────────

    @staticmethod
    def _guess_content_type(path: str) -> str:
        """Map file extensions to MIME types."""
        types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".mjs": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".webp": "image/webp",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
            ".eot": "application/vnd.ms-fontobject",
            ".txt": "text/plain; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".xml": "application/xml",
            ".pdf": "application/pdf",
        }
        ext = Path(path).suffix.lower()
        return types.get(ext, "application/octet-stream")

    # ── Logging ──────────────────────────────────────────────────────────

    def log_message(self, format, *args):
        """Override to suppress default stderr logging.

        Uncomment the line below to enable request logging to stderr:
            sys.stderr.write(f"[AgentBoard] {self.address_string()} - {format % args}\\n")
        """
        pass


# ── Server entry point ───────────────────────────────────────────────────

def main():
    """Start the AgentBoard HTTP server."""
    port = int(os.environ.get("AGENTBOARD_PORT", DEFAULT_PORT))
    host = os.environ.get("AGENTBOARD_HOST", "0.0.0.0")

    # Ensure database exists and is migrated
    get_db()

    # Print startup banner
    api_key = get_or_create_api_key()
    db_path = BASE_DIR / "agentboard.db"

    print("╔══════════════════════════════════════════╗")
    print("║          AgentBoard v0.1.0               ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  Database: {str(db_path):<30s}║")
    print(f"║  API Key:  {api_key:<30s}║")
    print(f"║  URL:      http://{host}:{port:<19}║")
    print(f"║  Auth:     Bearer {api_key[:20]}...{' ' * max(0, 9 - len(api_key[:20]))}║")
    print("╚══════════════════════════════════════════╝")
    print()
    print("Server started. Press Ctrl+C to stop.")

    server = HTTPServer((host, port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
