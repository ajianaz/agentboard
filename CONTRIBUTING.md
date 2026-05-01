# Contributing to AgentBoard

Thanks for your interest! Here's how to contribute.

## Development Setup

### ⚠️ Production Isolation

**If a production server is running from this repo, ALWAYS follow this protocol before switching branches:**

```bash
# 1. Check production state
ps aux | grep "server.py" | grep -v grep

# 2. Stash changes, keep production on main
git stash && git checkout main

# 3. Restart production from main, THEN checkout feature branch
git checkout -b feat/my-feature develop
```

`git checkout` changes working tree files that the running server uses. Switching branches without care can crash production or serve wrong code.

**Safer:** Clone to a separate directory for dev work.

```bash
git clone https://github.com/ajianaz/agentboard.git
cd agentboard
python -m pytest tests/ -v  # Verify tests pass
python server.py            # Start dev server (http://localhost:8765)
```

**Docker (optional):**
```bash
cp .env.example .env
docker compose up -d
```

### Side-by-Side with Production

If AgentBoard is already running in production, use a separate clone:

```bash
git clone -b develop https://github.com/ajianaz/agentboard.git ~/agentboard-dev
cd ~/agentboard-dev
AGENTBOARD_PORT=8766 python3 server.py   # Different port, different DB
```

This ensures production database and API key are never affected by development.

## Branch Strategy

```
main     ← production releases (protected, PR-only)
develop  ← integration branch (protected, PR-only)
  ↑
  ├── feat/xxx       ← feature branches (from develop, PR to develop)
  ├── fix/xxx        ← bug fix branches (from develop, PR to develop)
  ├── docs/xxx       ← documentation branches (from develop, PR to develop)
  └── refactor/xxx   ← refactoring branches (from develop, PR to develop)
```

### Rules

| Rule | Description |
|------|-------------|
| **2 permanent branches** | `main` and `develop` only — all others are temporary |
| **NEVER push directly** to `main` or `develop` | Always via pull request |
| **Feature branches from `develop`** | `git checkout -b feat/my-feature develop` |
| **PR target is `develop`** | Features land in develop first, then release to main |
| **Delete branch after merge** | Merged branches are deleted automatically |
| **Prefix convention** | `feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/` |

### Release Flow

```
develop  →  PR (release/vX.Y.Z)  →  main  →  GitHub Release + GHCR tag
```

1. Feature work accumulates on `develop`
2. When ready, create a release PR: `develop` → `main`
3. After merge, create GitHub Release with changelog
4. CI builds and pushes Docker image to GHCR

## Pull Request Process

1. **Create an issue** with milestone before coding
2. **Branch from `develop`**: `git checkout -b feat/my-feature develop`
3. **Make changes** — code, tests, docs
4. **Run tests**: `python -m pytest tests/ -v`
5. **Commit** with conventional commits (see below)
6. **Push** and open PR against `develop`
7. **Wait for review** (CodeRabbit + maintainer) before merge
8. **Branch is deleted** after merge

## Commit Convention

```
feat(scope): description      # New feature
fix(scope): description       # Bug fix
refactor(scope): description  # Code change without behavior change
test(scope): description      # Tests
docs(scope): description      # Documentation
chore(scope): description     # Maintenance
release(scope): description   # Release merge (develop → main)
```

**Examples:**
```
feat(webhooks): add file watcher for feedback ingestion
fix(auth): validate API key against server before saving
docs(readme): update Docker tag table
release: v1.5.3 — auth validation and dashboard polish
```

## Code Style

- Python: Follow PEP 8, use type hints where practical
- JavaScript: Clean, readable, commented for agent readability
- SQL: Uppercase keywords, lowercase identifiers
- All JSON columns must be valid JSON

## Testing

- All tests use in-memory SQLite (`:memory:`)
- Tests must not touch the filesystem
- Run: `python -m pytest tests/ -v`
- Target: 80%+ API coverage

## Reporting Issues

Use GitHub Issues with the provided templates. Include:
- Steps to reproduce
- Expected vs actual behavior
- Python version
- Browser (if frontend issue)

## Security Guidelines

### Credential Handling

- **NEVER** hardcode API keys, tokens, or secrets in source code
- Use `.env` files (outside repo) or environment variables
- `.api_key` file: `chmod 600`, `.gitignore` must include `.api_key` and `.env`
- Webhook endpoints: validate input, sanitize error messages, rate-limit

### Error Output

- Use `cred_safe.sanitize()` or equivalent for all exception output
- Never expose `str(exc)` or raw tracebacks in API responses
- Log full details server-side, return generic messages client-side

### Webhook Security

- All webhook endpoints must validate required fields
- Rate-limit per caller identity (agent_id or IP)
- Never trust client-provided data for authorization decisions

### Before Contributing

1. Run `git log -p | grep -iE '(api.key|secret|password|token).*=.*['\''"]'` — ensure no leaked credentials in history
2. Check `.gitignore` includes `.env`, `.api_key`, `*.db`, `__pycache__/`
3. New endpoints: add input validation and rate limiting
4. New dependencies: check for known CVEs, prefer stdlib

## Schema Migrations

When adding database changes:

1. Increment `SCHEMA_VERSION` in `db.py`
2. Add migration SQL to the `migrations` dict in `_run_migrations()`
3. Update the schema docs in `AGENTS.md`
4. Test migration from previous version (create DB with old schema, upgrade)
5. Migration must be backward-compatible (additive only, no column drops)
