# AgentBoard Pitfalls & Troubleshooting

## 1. Comments endpoint is NESTED
❌ `POST /api/comments` → 404
✅ `POST /api/tasks/{id}/comments` or `POST /api/pages/{id}/comments`

Comments live under their target resource, not at a top-level `/api/comments`.

---

## 2. Slug auto-increments on conflict
Creating a project named "Hermes Fleet" when `hermes-fleet` exists creates `hermes-fleet-2`.
**Fix:** Check existing slugs first via `GET /api/projects` before creating.

---

## 3. Auth header format
❌ `Authorization: Bearer ***` (literal asterisks)
✅ `Authorization: Bearer ab_aC2pm...7Zgk` (actual key from `.api_key`)

The `.api_key` file is auto-generated on first `python server.py` run.

---

## 4. Project slug vs Project ID
Most endpoints use **slug** (`/api/projects/{slug}`), but tasks use **ID** (`/api/tasks/{id}`).
Don't mix them up — slug is human-readable (`hermes-fleet`), ID is hex (`c72132cac29bc107`).

---

## 5. Timestamps are UTC in DB
SQLite stores `datetime('now')` which is UTC. Set `TZ=Asia/Jakarta` in `.env` for WIB display.
The server passes `TZ` through but the raw DB values are always UTC.

---

## 6. Port 8765 must be free
AgentBoard binds to the port in `.env` or default `8765`. If something else uses it:
- Check: `lsof -i :8765` or `ss -tlnp | grep 8765`
- Fix: Change `AGENTBOARD_PORT` in `.env`

---

## 7. `.api_key` is gitignored
The auto-generated API key is in `.api_key` which is `.gitignore`d.
When cloning fresh, you MUST run `python server.py` once to generate it.
The `onboard.py` script reads `.api_key` automatically.

---

## 8. Database file is gitignored
`agentboard.db` (and `-shm`, `-wal` files) are gitignored.
Production data lives only on the server. Use `/api/export` for backups.

---

## 9. Task status must match project's workflow
Each project has custom `statuses` (JSON array). Setting a task status that doesn't
match the project's defined statuses still works (no validation), but the UI may not
display it correctly. Stick to the project's defined status keys.

---

## 10. `include_archived=1` for full project list
`GET /api/projects` only returns active projects by default.
Use `?include_archived=1` to see archived ones.

---

## 11. DELETE is soft delete for projects
`DELETE /api/projects/{slug}` archives the project, not hard deletes.
Use `POST /api/projects/{slug}/restore` to unarchive.
Tasks and pages within archived projects are preserved.

---

## 12. Export/Import ID remapping
When importing, tasks and pages get **new IDs**. Parent-child relationships in pages
and comment target references are automatically remapped. But external references
(e.g., if you stored task IDs elsewhere) will break after import.

---

## 13. FTS5 search is ported-tokenized
Search uses `porter unicode61` tokenizer — it stems words.
Searching "deploying" matches "deploy" and "deployment".
Exact phrase search is not supported (FTS5 limitation).

---

## 14. Zero pip install — stdlib only
AgentBoard uses ONLY Python 3.11+ standard library (`tomllib`, `http.server`, `sqlite3`, `json`, `urllib`).
No `pip install` needed. No `requirements.txt`. If you see import errors for third-party packages,
something is wrong with your Python environment.
