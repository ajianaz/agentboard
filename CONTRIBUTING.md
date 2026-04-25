# Contributing to AgentBoard

Thanks for your interest! Here's how to contribute.

## Development Setup

```bash
git clone https://github.com/ajianaz/agentboard.git
cd agentboard
python -m pytest tests/ -v  # Verify tests pass
python server.py            # Start dev server
```

## Branch Strategy

- `main` — tagged releases only
- `develop` — integration branch
- `feat/*` — new features (branch from `develop`)
- `fix/*` — bug fixes (branch from `develop`)

## Pull Request Process

1. Create a branch from `develop`: `git checkout -b feat/my-feature develop`
2. Make changes with tests
3. Commit with conventional commits: `feat(api): add task filtering`
4. Push and open PR against `develop`
5. Ensure CI passes
6. Wait for review

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
