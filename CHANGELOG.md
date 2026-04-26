# Changelog

All notable changes to AgentBoard are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.3.0] - Unreleased

### Added
- **Analytics Engine** — KPI computation with configurable intervals (5min default), auto-cleanup of stale data
- **KPI API** — `/api/analytics/summary`, `/api/analytics/agents`, `/api/analytics/trends`, `/api/analytics/recompute`
- **Activity Log** — Full audit trail with filters (agent, action, project, date range, limit)
- **Discussion System** — Create discussions with participants, collect structured feedback, auto-generate summaries
- **Discussion API** — 7 endpoints: CRUD + feedback + summary + project filtering
- **Security Test Suite** — 94 tests covering auth bypass, SQL injection, XSS, path traversal, FTS5 injection, payload handling, auth key management, input validation, CORS, database security
- **CI Pipeline** — GitHub Actions with unit, security, analytics, integration tests + standalone verify
- **Agent Profile Discussions** — Per-agent discussion threads for coordination and feedback

### Changed
- **CORS fix** — `do_OPTIONS` now sends status line before headers (was reversed, caused `BadStatusLine`)
- **KPI engine date format** — Fixed `T00:00:00Z` → `00:00:00` to match activity log format
- **KPI engine action names** — Aligned with actual API logging (`created`/`updated`/`status changed`)
- **KPI LIKE patterns** — Added space after colon in JSON patterns (`"key": "value"`)

### Security
- All 10 f-string SQL patterns audited — confirmed safe (hardcoded fragments, parameterized values)
- FTS5 query injection identified and documented (server returns 500 on malformed queries)
- Path traversal protected via `resolve().relative_to()` in static file handler
- Auth keys stored as SHA-256 hashes — no plaintext

## [1.2.0] - 2025-04-24

### Added
- Multi-project kanban board
- Agent profile system (role, status, capabilities)
- HITL (Human-In-The-Loop) approval workflow
- FTS5 full-text search
- Export/Import as JSON
- Dark theme UI
- API key authentication (POST/PATCH/DELETE)
- `AGENTS.md` for agent onboarding

## [1.1.0] - 2025-04-15

### Added
- Basic task CRUD
- Project management
- Static file serving

## [1.0.0] - 2025-04-01

### Added
- Initial release
- Python stdlib HTTP server
- SQLite storage
