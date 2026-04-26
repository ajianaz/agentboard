"""API Router — maps URL paths to handler functions."""

from urllib.parse import parse_qs


class Router:
    """Simple regex-free router. Routes are registered as (method, pattern) → handler."""

    def __init__(self):
        self.routes = []

    def add(self, method: str, pattern: str, handler):
        """Register a route. Use {param} for path parameters."""
        self.routes.append((method.upper(), pattern, handler))

    def get(self, pattern: str):
        """Decorator for GET routes."""
        def decorator(fn):
            self.add('GET', pattern, fn)
            return fn
        return decorator

    def post(self, pattern: str):
        """Decorator for POST routes."""
        def decorator(fn):
            self.add('POST', pattern, fn)
            return fn
        return decorator

    def patch(self, pattern: str):
        """Decorator for PATCH routes."""
        def decorator(fn):
            self.add('PATCH', pattern, fn)
            return fn
        return decorator

    def delete(self, pattern: str):
        """Decorator for DELETE routes."""
        def decorator(fn):
            self.add('DELETE', pattern, fn)
            return fn
        return decorator

    def handle(self, method: str, path: str, query: dict, body: bytes, headers: dict):
        """Match and execute a route. Returns (status, data) or None."""
        for route_method, pattern, handler in self.routes:
            if route_method != method.upper():
                continue
            params = self._match(pattern, path)
            if params is not None:
                try:
                    return handler(params, query, body, headers)
                except Exception as e:
                    return 500, {"error": str(e), "code": "INTERNAL_ERROR"}
        return None

    def _match(self, pattern: str, path: str) -> dict | None:
        """Match pattern against path. Returns dict of params or None.

        Supports {param} placeholders in the pattern.
        Example: '/api/projects/{slug}' matches '/api/projects/marketing'
                 → returns {'slug': 'marketing'}
        """
        pattern_parts = pattern.strip('/').split('/')
        path_parts = path.strip('/').split('/')

        if len(pattern_parts) != len(path_parts):
            return None

        params = {}
        for pp, pathp in zip(pattern_parts, path_parts):
            if pp.startswith('{') and pp.endswith('}'):
                params[pp[1:-1]] = pathp
            elif pp != pathp:
                return None
        return params


# Global router instance
router = Router()

# Route modules will be imported here when they exist
# Each module calls router.get/post/patch/delete to register its routes.
# from api import projects, tasks, pages, agents, comments, activity, search
_ROUTE_MODULES = [
    "projects", "tasks", "pages", "agents", "comments", "activity", "search", "export",
    "auth_keys", "analytics", "discussions",
]
for _mod_name in _ROUTE_MODULES:
    try:
        __import__(f"api.{_mod_name}")
    except ImportError:
        pass
