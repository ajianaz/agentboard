# Changelog

All notable changes to AgentBoard are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [1.5.3] - 2026-04-28

### Fixed
- Validate API key against server before saving — prevents stale/invalid keys
- Reorder public dashboard cards — Total, Done, Review, In Progress, To Do, Proposed

## [1.5.2] - 2026-04-28

### Added
- **Review & To Do cards** on public dashboard — split overview into actionable views

## [1.5.1] - 2026-04-27

### Fixed
- Docs: fix stale refs — schema v7, 54 endpoints, complete api_reference
- CodeRabbit PR #105 — stale projSlug ref, hidden projects leak in public stats

## [1.5.0] - 2026-04-27

### Added
- **Visibility Model v2** — Per-page visibility control (public/private) in docs hub
- **Standalone Webhook** — Direct delivery to AgentBoard without http_router relay, with HMAC-SHA256 signing
- **Webhook Task Update** — `/api/webhook/task` endpoint for external activity logging
- **Public Stats API** — `/api/stats/public` for anonymized board statistics
- **Split Pending View** — Overview dashboard separates Todo and In Review counts
- **Discussion Webhook Ports** — Configurable ports per discussion for multi-agent coordination
- **Discussion Zombie Mitigation** — Auto-detection and cleanup of stalled discussions

### Changed
- **UI Refactor** — Merged Home + Dashboard into single Overview page
- **Sidebar** — Analytics and Agents sections hidden from default sidebar
- **PR #105 fixes** — Stale projSlug reference, hidden projects no longer leak in public stats

### Fixed
- Pages API visibility filter used wrong table alias (pg → p/c)
- Migration v7 idempotent — skips duplicate column errors gracefully
- Migration v7 — drops FTS before pages rebuild, adds error logging
- Stats totals inconsistent — filter non-archived, add todo_tasks count

## [1.4.0] - 2026-04-26

### Added
- **Standalone Tools** — `tools/client.py` for HTTP API client and `tools/discussion.py` for discussion management
- **Agent Sync** — Hermes agent fleet integration via direct webhooks
- **Public Readiness** — Repo cleaned for public cloning (no secrets, generic docs)

### Changed
- **Documentation** — Made repo generic (removed Hermes-specific references from public docs)
- **Gitignore** — Added *.db, *.db-shm, *.db-wal, .api_key, .env to prevent secret leaks

## [1.3.0] - 2026-04-25

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
