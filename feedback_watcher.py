"""feedback_watcher.py — File-based feedback ingestion for AgentBoard.

Standalone feature: monitors a directory for new feedback files and
automatically inserts them into the discussion_feedback table.

No external dependencies — uses only Python stdlib.

File naming convention:
    {discussion_id}/{agent}_{round}.md
    {discussion_id}/{agent}_feedback.md     (round auto-detected from subfolder)
    {discussion_id}/round{N}/{agent}.md      (nested round folders)

Configuration (agentboard.toml):
    [feedback_watcher]
    enabled = true
    directory = "/path/to/feedback"   # absolute or relative to BASE_DIR
    poll_interval = 5                 # seconds
    processed_marker = ".ingested"     # touch this file after ingestion

How it works:
    1. Background thread polls the directory every N seconds
    2. On new file → parse discussion_id, agent, round from path
    3. Insert into discussion_feedback table
    4. Update discussion current_round
    5. Touch .ingested marker to avoid re-processing
    6. Log to activity table
"""

import json
import os
import re
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

WIB = timezone(timedelta(hours=7))


class FeedbackWatcher:
    """Watches a directory for feedback files and syncs to AgentBoard DB."""

    def __init__(self, db_path: str, watch_dir: str, poll_interval: int = 5,
                 enabled: bool = True):
        self.db_path = db_path
        self.watch_dir = Path(watch_dir)
        self.poll_interval = poll_interval
        self.enabled = enabled
        self._running = False
        self._thread = None
        self._processed = set()  # set of absolute file paths already ingested

    def start(self):
        """Start the watcher thread."""
        if not self.enabled:
            return
        if not self.watch_dir.exists():
            self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"  Feedback : WATCHING {self.watch_dir} (every {self.poll_interval}s)")

    def stop(self):
        """Stop the watcher thread."""
        self._running = False

    def _loop(self):
        """Main polling loop."""
        # Initial scan — mark existing files as processed (avoid re-ingestion on restart)
        self._scan_existing()

        while self._running:
            try:
                self._scan_new()
            except Exception as e:
                print(f"  [feedback_watcher] Error: {e}")
            time.sleep(self.poll_interval)

    def _scan_existing(self):
        """Mark all existing files as already processed (skip on restart)."""
        if not self.watch_dir.exists():
            return
        for disc_dir in self.watch_dir.iterdir():
            if not disc_dir.is_dir():
                continue
            for f in self._iter_feedback_files(disc_dir):
                self._processed.add(str(f.resolve()))
        if self._processed:
            print(f"  Feedback : skipped {len(self._processed)} existing files")

    def _scan_new(self):
        """Scan for new feedback files and ingest them."""
        if not self.watch_dir.exists():
            return

        for disc_dir in self.watch_dir.iterdir():
            if not disc_dir.is_dir():
                continue
            discussion_id = disc_dir.name
            for f in self._iter_feedback_files(disc_dir):
                abs_path = str(f.resolve())
                if abs_path in self._processed:
                    continue
                # Check for .ingested marker
                marker = Path(abs_path + ".ingested")
                if marker.exists():
                    self._processed.add(abs_path)
                    continue
                # Try to ingest
                try:
                    self._ingest(discussion_id, f)
                    marker.touch()
                    self._processed.add(abs_path)
                except Exception as e:
                    # Don't mark as processed — retry next poll
                    print(f"  [feedback_watcher] Failed to ingest {f}: {e}")

    def _iter_feedback_files(self, disc_dir: Path):
        """Yield all feedback markdown files in a discussion directory.

        Supports these structures:
            {disc_dir}/{agent}_{round}.md
            {disc_dir}/{agent}_feedback.md
            {disc_dir}/round{N}/{agent}.md
            {disc_dir}/round{N}/{agent}_feedback.md
        """
        if not disc_dir.exists():
            return

        # Direct files in disc_dir
        for f in disc_dir.iterdir():
            if f.is_file() and f.suffix == ".md" and not f.name.startswith("."):
                yield f

        # Nested round folders: round1/, round2/, round10/
        for round_dir in sorted(disc_dir.iterdir()):
            if not round_dir.is_dir():
                continue
            if re.match(r"round\d+", round_dir.name, re.IGNORECASE):
                for f in round_dir.iterdir():
                    if f.is_file() and f.suffix == ".md" and not f.name.startswith("."):
                        yield f

    def _parse_filename(self, disc_dir: Path, f: Path) -> dict:
        """Parse agent name and round number from file path and name.

        Returns dict with: agent, round, content (read from file)
        """
        # Read content
        content = f.read_text(encoding="utf-8", errors="replace").strip()
        if len(content) < 10:
            raise ValueError(f"File too short ({len(content)} chars)")

        # Determine if inside a round subfolder
        round_from_dir = None
        parent_name = f.parent.name
        round_match = re.match(r"round(\d+)", parent_name, re.IGNORECASE)
        if round_match:
            round_from_dir = int(round_match.group(1))

        # Parse agent and round from filename
        stem = f.stem  # e.g. "sosmed_feedback", "cto_3", "kai", "badsector_2"
        agent = None
        round_from_name = None

        # Pattern: {agent}_{round}  (e.g. "sosmed_2", "cto_1")
        m = re.match(r"^(.+?)_(\d+)$", stem)
        if m:
            agent = m.group(1).lower()
            round_from_name = int(m.group(2))
        # Pattern: {agent}_feedback  (e.g. "sosmed_feedback", "kai_feedback")
        elif stem.endswith("_feedback"):
            agent = stem.rsplit("_feedback", 1)[0].lower()
        # Pattern: just agent name  (e.g. "sosmed", "cto")
        else:
            agent = stem.lower()

        if not agent:
            raise ValueError(f"Cannot parse agent from filename: {f.name}")

        # Determine round: explicit > dir > default 1
        round_num = round_from_name or round_from_dir or 1

        return {
            "agent": agent,
            "round": round_num,
            "content": content,
            "word_count": len(content.split()),
            "file_path": str(f),
        }

    def _ingest(self, discussion_id: str, f: Path):
        """Parse and insert a feedback file into the database."""
        parsed = self._parse_filename(f.parent, f)

        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Verify discussion exists
        disc = conn.execute(
            "SELECT id, title, current_round, status FROM discussions WHERE id=?",
            (discussion_id,)
        ).fetchone()

        if not disc:
            print(f"  [feedback_watcher] Unknown discussion: {discussion_id} (from {f.name})")
            conn.close()
            return

        disc = dict(disc)

        # Check for duplicate feedback (same discussion + agent + round)
        existing = conn.execute(
            "SELECT id FROM discussion_feedback WHERE discussion_id=? AND participant=? AND round=?",
            (discussion_id, parsed["agent"], parsed["round"])
        ).fetchone()

        if existing:
            # Update existing feedback instead of duplicate insert
            conn.execute(
                """UPDATE discussion_feedback
                   SET content=?, word_count=?, created_at=?
                   WHERE discussion_id=? AND participant=? AND round=?""",
                (parsed["content"], parsed["word_count"],
                 datetime.now(WIB).strftime("%Y-%m-%dT%H:%M:%S+07:00"),
                 discussion_id, parsed["agent"], parsed["round"])
            )
            action = "updated"
        else:
            # Insert new feedback
            fb_id = parsed["agent"][:8] + "-" + discussion_id[:8] + "-r" + str(parsed["round"])
            ts = datetime.now(WIB).strftime("%Y-%m-%dT%H:%M:%S+07:00")

            # Determine verdict from content (best-effort heuristic)
            verdict = self._detect_verdict(parsed["content"])

            conn.execute(
                """INSERT INTO discussion_feedback
                   (id, discussion_id, round, participant, role, verdict, content, word_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fb_id, discussion_id, parsed["round"], parsed["agent"],
                 "", verdict, parsed["content"], parsed["word_count"], ts)
            )
            action = "inserted"

        # Update discussion current_round if this round is higher
        if parsed["round"] > disc["current_round"]:
            conn.execute(
                "UPDATE discussions SET current_round=?, updated_at=? WHERE id=?",
                (parsed["round"],
                 datetime.now(WIB).strftime("%Y-%m-%dT%H:%M:%S+07:00"),
                 discussion_id)
            )

        # Log to activity
        ts = datetime.now(WIB).strftime("%Y-%m-%dT%H:%M:%S+07:00")
        try:
            conn.execute(
                """INSERT INTO activity (id, project_id, target_type, target_id, action, actor, detail, created_at)
                   VALUES (?, '', 'discussion', ?, ?, ?, ?, ?)""",
                (fb_id if action == "inserted" else "upd-" + fb_id,
                 discussion_id,
                 "feedback_file_ingest" if action == "inserted" else "feedback_file_update",
                 parsed["agent"],
                 json.dumps({
                     "round": parsed["round"],
                     "word_count": parsed["word_count"],
                     "file": f.name,
                     "action": action,
                 }),
                 ts)
            )
        except Exception:
            pass  # activity log is best-effort

        conn.commit()
        conn.close()

        print(f"  [feedback_watcher] {action}: {parsed['agent']} R{parsed['round']} "
              f"({parsed['word_count']}w) → {discussion_id[:12]}")

    def _detect_verdict(self, content: str) -> str:
        """Best-effort verdict detection from feedback content.

        Checks for common patterns like "approve", "reject", "conditional".
        Returns empty string if uncertain (AgentBoard allows empty verdict).
        """
        content_lower = content[:500].lower()

        # Explicit reject signals
        reject_signals = ["verdict: reject", "❌ reject", "rejected", "tidak setuju", "vote: reject"]
        for sig in reject_signals:
            if sig in content_lower:
                return "reject"

        # Explicit conditional signals
        cond_signals = ["conditional", "approved with notes", "approved_with", "setuju dengan catatan", " ⚠️"]
        for sig in cond_signals:
            if sig in content_lower:
                return "conditional"

        # Explicit approve signals
        approve_signals = ["verdict: approve", "✅", "approve", "setuju", "agreed", "looks good"]
        for sig in approve_signals:
            if sig in content_lower:
                return "approve"

        # Default: empty (let UI/API decide)
        return ""

    def ingest_file(self, file_path: str) -> dict:
        """Manually ingest a single file (for API use).

        Returns dict with status and details.
        """
        f = Path(file_path)
        if not f.exists():
            return {"status": "error", "error": "File not found"}

        # Determine discussion_id from parent directory name
        disc_dir = f.parent
        discussion_id = disc_dir.name

        try:
            self._ingest(discussion_id, f)
            # Mark as processed
            Path(str(f.resolve()) + ".ingested").touch()
            self._processed.add(str(f.resolve()))
            return {"status": "ok", "discussion_id": discussion_id}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def status(self) -> dict:
        """Return watcher status for health checks."""
        return {
            "enabled": self.enabled,
            "running": self._running,
            "watch_dir": str(self.watch_dir),
            "watch_dir_exists": self.watch_dir.exists(),
            "processed_files": len(self._processed),
            "poll_interval": self.poll_interval,
        }
