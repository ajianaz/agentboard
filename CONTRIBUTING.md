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
git checkout -b feat/my-feature main
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
git clone -b develop https://github.com/ajianaz/agentboard.git /opt/data/agentboard-dev
cd /opt/data/agentboard-dev
AGENTBOARD_PORT=8766 python3 server.py   # Different port, different DB
```

This ensures production database and API key are never affected by development.

## Branch Strategy

- `main` — production releases. **NEVER push directly** — always via PR
- `feature/*` — new features (branch from `main`, PR back to `main`)
- `fix/*` — bug fixes (branch from `main`, PR back to `main`)

## Pull Request Process

1. Create issues + milestone before coding
2. Create a branch from `main`: `git checkout -b feature/my-feature main`
3. Update documentation **before** committing code changes
4. Commit with conventional commits: `feat(api): add task filtering`
5. Push and open PR against `main`
6. Wait for review before merge

## Commit Convention

```
feat(scope): description     # New feature
fix(scope): description      # Bug fix
refactor(scope): description # Code change
test(scope): description     # Tests
docs(scope): description     # Documentation
chore(scope): description    # Maintenance
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
