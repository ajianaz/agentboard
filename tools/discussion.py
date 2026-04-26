#!/usr/bin/env python3
"""Multi-agent discussion coordinator — transport-agnostic, zero pip dependencies.

Delivers discussion requests to agent endpoints via a pluggable send function,
then collects feedback by polling files written by agents.

Manages discussion sessions between agents:
  - Create session with file-based shared workspace
  - Send review requests to participants via injectable transport (webhook, API, MQ, etc.)
  - Collect feedback via file polling
  - Track rounds and synthesize results

Usage:
  from tools.discussion import DiscussionSession

  def my_send_fn(agent, payload):
      import urllib.request, json
      url = f"http://your-gateway/{agent}/webhooks/discussion"
      data = json.dumps(payload).encode()
      req = urllib.request.Request(url, data=data, method="POST")
      req.add_header("Content-Type", "application/json")
      resp = urllib.request.urlopen(req, timeout=15)
      return resp.status == 200

  disc = DiscussionSession(
      topic="Feature Review — Auth Module",
      leader="agent-alpha",
      participants=["agent-beta", "agent-gamma"],
      phase="concept",
      max_rounds=3
  )
  disc.create()
  disc.write_leader_draft("# Draft\\n\\n...")
  disc.send_round_request(send_fn=my_send_fn)
  feedback = disc.collect_feedback(timeout=60)
  disc.write_synthesis("# Synthesis\\n\\n...")
  disc.close()

CLI:
  python -m tools.discussion create --topic "Review" --leader agent-alpha --participants agent-beta,agent-gamma
  python -m tools.discussion list
  python -m tools.discussion status <session_id>
"""

__all__ = [
    "DiscussionSession",
    "list_sessions",
    "get_session",
    "cleanup_old_sessions",
    "main",
]

import json
import os
import sys
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

WIB = timezone(timedelta(hours=7))
BASE_DIR = os.environ.get("DISCUSSION_BASE_DIR", "./discussions")
os.makedirs(BASE_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("discussion")

# Agent name → discussion role (generic examples)
AGENT_ROLES = {
    "alpha": "Reviewer",
    "beta": "QA Specialist",
    "gamma": "Data Analyst",
}

# Default focus per agent
DEFAULT_FOCUS = {
    "alpha": "general review",
    "beta": "quality assurance",
    "gamma": "data validation",
}

# Path to config file (same directory as this module)
_CONFIG_PATH = Path(__file__).parent / "discussion_config.json"


def _load_send_fn_from_config():
    """Try to build a send function from discussion_config.json.

    Config format:
    {
        "endpoints": {
            "agent-alpha": "http://localhost:8100/webhooks/discussion",
            "agent-beta": "http://localhost:8101/webhooks/discussion"
        },
        "hmac_key": "optional-shared-key"
    }

    Returns a callable(agent, payload) -> bool, or None if no config found.
    """
    if not _CONFIG_PATH.exists():
        return None

    try:
        with open(_CONFIG_PATH) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Cannot parse {_CONFIG_PATH}: {e}")
        return None

    endpoints = config.get("endpoints")
    if not endpoints or not isinstance(endpoints, dict):
        log.warning(f"No 'endpoints' in {_CONFIG_PATH}")
        return None

    hmac_key = config.get("hmac_key")

    def _config_send_fn(agent, payload):
        """Send discussion payload to agent via configured endpoint."""
        url = endpoints.get(agent)
        if not url:
            log.error(f"No endpoint configured for agent '{agent}' in {_CONFIG_PATH}")
            return False

        import urllib.request
        import hashlib
        import hmac as hmac_mod

        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")

        if hmac_key:
            sig = hmac_mod.new(
                hmac_key.encode(), data, hashlib.sha256
            ).hexdigest()
            req.add_header("X-Hub-Signature-256", f"sha256={sig}")

        try:
            resp = urllib.request.urlopen(req, timeout=15)
            return resp.status == 200
        except Exception as e:
            log.error(f"Failed to send to {agent} at {url}: {e}")
            return False

    return _config_send_fn


class DiscussionSession:
    """Manages a single discussion session between agents."""

    def __init__(
        self,
        topic: str,
        leader: str = "alpha",
        participants: list = None,
        phase: str = "general",
        max_rounds: int = 3,
        feedback_max_words: int = 500,
        session_id: str = None,
        description: str = "",
    ):
        self.topic = topic
        self.leader = leader
        self.participants = participants or ["alpha", "beta"]
        self.phase = phase  # research, concept, outline, general
        self.max_rounds = max_rounds
        self.feedback_max_words = feedback_max_words
        self.description = description

        # Generate or use provided session ID
        if session_id:
            self.session_id = session_id
        else:
            slug = topic.lower().replace(" ", "-")[:30]
            slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)
            ts = datetime.now(WIB).strftime("%Y%m%d-%H%M%S")
            self.session_id = f"disc-{ts}-{slug}"

        # Session directory
        self.session_dir = os.path.join(BASE_DIR, self.session_id)
        self.metadata_path = os.path.join(self.session_dir, "metadata.json")

        # State
        self._round = 0
        self._status = "created"  # created, in_progress, collecting, completed, cancelled
        self._created_at = None
        self._updated_at = None

        # Track sent message IDs for feedback collection
        self._sent_msg_ids = {}  # agent -> msg_id (per round)

    @property
    def current_round(self):
        return self._round

    @property
    def status(self):
        return self._status

    @property
    def is_final_round(self):
        return self._round >= self.max_rounds

    def round_dir(self, round_num=None):
        """Get directory path for a specific round."""
        r = round_num if round_num else self._round
        return os.path.join(self.session_dir, f"round{r}")

    def round_path(self, filename, round_num=None):
        """Get file path within a round directory."""
        return os.path.join(self.round_dir(round_num), filename)

    def create(self):
        """Create session directory and metadata."""
        os.makedirs(self.session_dir, exist_ok=True)
        now = datetime.now(WIB).isoformat()
        self._created_at = now
        self._updated_at = now

        metadata = {
            "session_id": self.session_id,
            "topic": self.topic,
            "description": self.description,
            "leader": self.leader,
            "participants": self.participants,
            "phase": self.phase,
            "max_rounds": self.max_rounds,
            "feedback_max_words": self.feedback_max_words,
            "status": "created",
            "current_round": 0,
            "created_at": now,
            "updated_at": now,
            "rounds": [],
        }

        with open(self.metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Create context file
        context_path = os.path.join(self.session_dir, "context.md")
        with open(context_path, "w") as f:
            f.write(f"# Discussion: {self.topic}\n\n")
            f.write(f"- **Leader:** {self.leader} ({AGENT_ROLES.get(self.leader, 'Lead')})\n")
            f.write(f"- **Phase:** {self.phase}\n")
            f.write(f"- **Max Rounds:** {self.max_rounds}\n")
            f.write(f"- **Participants:**\n")
            for p in self.participants:
                role = AGENT_ROLES.get(p, "Participant")
                f.write(f"  - {p} ({role})\n")
            f.write(f"\n## Discussion Log\n\n")

        log.info(f"Session created: {self.session_id}")
        return self

    def _update_metadata(self, **kwargs):
        """Update metadata file."""
        if not os.path.exists(self.metadata_path):
            return

        with open(self.metadata_path) as f:
            metadata = json.load(f)

        for key, value in kwargs.items():
            metadata[key] = value
        metadata["updated_at"] = datetime.now(WIB).isoformat()

        with open(self.metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def write_leader_draft(self, content: str, filename="leader_draft.md", round_num=None):
        """Write leader's draft/proposal for current round.

        If round_num is None, auto-starts at round 1 (first round).
        This ensures draft and send_round_request use the same round directory.
        """
        r = round_num if round_num else 1
        if not round_num and self._round < 1:
            self._round = 1
        round_d = self.round_dir(r)
        os.makedirs(round_d, exist_ok=True)

        path = os.path.join(round_d, filename)
        with open(path, "w") as f:
            f.write(content)

        log.info(f"Leader draft written: {path} ({len(content)} chars)")
        return path

    def write_synthesis(self, content: str, filename="leader_synthesis.md", round_num=None):
        """Write leader's synthesis of feedback."""
        return self.write_leader_draft(content, filename, round_num)

    def send_round_request(
        self,
        focus_per_agent: dict = None,
        round_num: int = None,
        send_fn=None,
    ) -> dict:
        """Send discussion request to all participants.

        Uses an injectable send function for transport-agnostic delivery.
        If send_fn is not provided, tries to load from discussion_config.json.

        Args:
            focus_per_agent: Dict of {agent_name: focus_instruction} for per-agent customization.
                            Falls back to DEFAULT_FOCUS if not specified.
            round_num: Override round number (default: current round)
            send_fn: Callable(agent, payload) -> bool. If None, loads from config.

        Returns:
            Dict of {agent_name: True/False} indicating send success.
        """
        r = round_num if round_num else self._round

        if r == 0:
            r = 1
            self._round = 1

        round_d = self.round_dir(r)
        os.makedirs(round_d, exist_ok=True)

        # Resolve send function
        actual_send_fn = send_fn
        if actual_send_fn is None:
            actual_send_fn = _load_send_fn_from_config()
        if actual_send_fn is None:
            raise ValueError(
                "No send function available. Either:\n"
                "  1. Pass send_fn to send_round_request(), or\n"
                "  2. Create discussion_config.json alongside this file with an 'endpoints' map.\n"
                f"   Expected config path: {_CONFIG_PATH}"
            )

        sent = {}
        for agent in self.participants:
            # Determine focus
            focus = (focus_per_agent or {}).get(
                agent, DEFAULT_FOCUS.get(agent, "general review")
            )

            # File paths
            draft_path = self.round_path("leader_draft.md", r)
            feedback_path = self.round_path(f"{agent}_feedback.md", r)

            # Build instruction
            instruction = (
                f"You are invited to a discussion: {self.topic}\n\n"
                f"**Round:** {r}/{self.max_rounds}\n"
                f"**Phase:** {self.phase}\n"
                f"**Review focus:** {focus}\n\n"
                f"1. Read the draft at: {draft_path}\n"
                f"2. Review per your role ({AGENT_ROLES.get(agent, 'participant')})\n"
                f"3. Write feedback to: {feedback_path}\n"
                f"4. Max {self.feedback_max_words} words\n"
            )

            # Build payload
            payload = {
                "round": r,
                "max_rounds": self.max_rounds,
                "topic": self.topic,
                "leader": self.leader,
                "agent_role": AGENT_ROLES.get(agent, "Participant"),
                "instruction": instruction,
                "discussion_id": self.session_id,
                "phase": self.phase,
                "draft_path": draft_path,
                "feedback_path": feedback_path,
                "focus": focus,
                "feedback_max_words": self.feedback_max_words,
            }

            try:
                ok = actual_send_fn(agent, payload)
                sent[agent] = ok
                msg_id = uuid.uuid4().hex[:12]
                self._sent_msg_ids[agent] = msg_id
                if ok:
                    log.info(f"Request sent to {agent}: [DISC] {self.topic} (Round {r}/{self.max_rounds})")
                else:
                    log.error(f"Send failed for {agent}: send_fn returned False")
            except Exception as e:
                log.error(f"Failed to send to {agent}: {e}")
                sent[agent] = False

        # Update metadata
        self._update_metadata(
            status="collecting",
            current_round=r,
            sent_msg_ids=sent,
        )
        self._status = "collecting"

        return sent

    def collect_feedback(self, timeout: int = 60) -> dict:
        """Collect feedback from participants via file polling.

        Agents write their feedback to {feedback_path} after processing
        the discussion request. This method polls those files until all
        participants respond or timeout is reached.

        Args:
            timeout: Max seconds to wait for all participants

        Returns:
            Dict of {agent_name: feedback_text_or_None}
        """
        r = self._round
        feedback = {agent: None for agent in self.participants}

        # ── Wait for all feedback via file polling ──
        start = time.time()
        while time.time() - start < timeout:
            all_done = True
            for agent in self.participants:
                if feedback[agent] is not None:
                    continue
                feedback_path = self.round_path(f"{agent}_feedback.md", r)
                if os.path.exists(feedback_path):
                    try:
                        with open(feedback_path) as f:
                            content = f.read().strip()
                        if len(content) > 20:
                            feedback[agent] = content
                            log.info(f"Feedback from {agent}: {len(content)} chars")
                            continue
                    except Exception:
                        break
                all_done = False

            if all_done:
                break
            time.sleep(2)

        # Log timeouts
        for agent, fb in feedback.items():
            if fb is None:
                log.warning(f"Timeout waiting for feedback from {agent} ({timeout}s)")

        # Update metadata
        received = {k: v is not None for k, v in feedback.items()}
        self._update_metadata(
            status="in_progress",
            feedback_received=received,
        )

        return feedback

    def next_round(self):
        """Advance to next round. Returns False if max rounds reached."""
        if self._round >= self.max_rounds:
            log.warning(f"Max rounds reached ({self.max_rounds})")
            return False

        self._round += 1
        self._status = "in_progress"

        # Create round directory
        os.makedirs(self.round_dir(), exist_ok=True)

        self._update_metadata(current_round=self._round)
        log.info(f"Advanced to round {self._round}/{self.max_rounds}")
        return True

    def close(self, status="completed"):
        """Close the discussion session."""
        self._status = status
        self._update_metadata(status=status)

        # Append summary to context
        context_path = os.path.join(self.session_dir, "context.md")
        summary = (
            f"\n---\n\n"
            f"## Session Closed\n"
            f"- **Status:** {status}\n"
            f"- **Rounds completed:** {self._round}\n"
            f"- **Closed at:** {datetime.now(WIB).strftime('%Y-%m-%d %H:%M:%S')} WIB\n"
        )

        with open(context_path, "a") as f:
            f.write(summary)

        log.info(f"Session closed: {self.session_id} ({status})")

    def get_feedback(self, agent: str, round_num: int = None) -> str | None:
        """Read feedback from a specific agent for a specific round."""
        r = round_num if round_num else self._round
        path = self.round_path(f"{agent}_feedback.md", r)

        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
        return None

    def get_all_feedback(self, round_num: int = None) -> dict:
        """Read all feedback for a specific round."""
        r = round_num if round_num else self._round
        result = {}
        for agent in self.participants:
            fb = self.get_feedback(agent, r)
            if fb:
                result[agent] = fb
        return result

    def get_metadata(self) -> dict:
        """Read session metadata."""
        if os.path.exists(self.metadata_path):
            with open(self.metadata_path) as f:
                return json.load(f)
        return {}

    def summary(self) -> str:
        """Generate a text summary of the discussion session."""
        meta = self.get_metadata()
        lines = [
            f"## Discussion: {self.topic}",
            f"- **Session ID:** {self.session_id}",
            f"- **Status:** {self._status}",
            f"- **Leader:** {self.leader}",
            f"- **Participants:** {', '.join(self.participants)}",
            f"- **Phase:** {self.phase}",
            f"- **Rounds:** {self._round}/{self.max_rounds}",
            f"- **Created:** {self._created_at}",
            f"- **Dir:** {self.session_dir}",
        ]

        # Feedback summary per round
        for r in range(1, self._round + 1):
            lines.append(f"\n### Round {r}")
            fb = self.get_all_feedback(r)
            if fb:
                for agent, content in fb.items():
                    preview = content[:100].replace("\n", " ")
                    lines.append(f"- **{agent}:** {preview}...")
            else:
                lines.append("- (no feedback received)")

        return "\n".join(lines)


def list_sessions() -> list:
    """List all discussion sessions."""
    sessions = []
    if not os.path.exists(BASE_DIR):
        return sessions

    for dir_name in sorted(os.listdir(BASE_DIR)):
        meta_path = os.path.join(BASE_DIR, dir_name, "metadata.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                sessions.append(meta)
            except Exception:
                sessions.append({"session_id": dir_name, "status": "unknown"})
    return sessions


def get_session(session_id: str) -> DiscussionSession | None:
    """Load an existing session by ID."""
    meta_path = os.path.join(BASE_DIR, session_id, "metadata.json")
    if not os.path.exists(meta_path):
        return None

    try:
        with open(meta_path) as f:
            meta = json.load(f)
        disc = DiscussionSession(
            topic=meta["topic"],
            leader=meta["leader"],
            participants=meta["participants"],
            phase=meta["phase"],
            max_rounds=meta["max_rounds"],
            feedback_max_words=meta.get("feedback_max_words", 500),
            session_id=meta["session_id"],
        )
        disc._round = meta.get("current_round", 0)
        disc._status = meta.get("status", "unknown")
        disc._created_at = meta.get("created_at")
        return disc
    except Exception as e:
        log.error(f"Failed to load session {session_id}: {e}")
        return None


def cleanup_old_sessions(max_age_hours: int = 24):
    """Remove discussion sessions older than max_age_hours."""
    cutoff = time.time() - (max_age_hours * 3600)
    removed = 0

    if not os.path.exists(BASE_DIR):
        return removed

    for dir_name in os.listdir(BASE_DIR):
        session_path = os.path.join(BASE_DIR, dir_name)
        if not os.path.isdir(session_path):
            continue

        # Check metadata
        meta_path = os.path.join(session_path, "metadata.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                created = meta.get("created_at", "")
                if created:
                    dt = datetime.fromisoformat(created)
                    if dt.timestamp() < cutoff:
                        import shutil
                        shutil.rmtree(session_path)
                        removed += 1
                        log.info(f"Cleaned up old session: {dir_name}")
            except Exception:
                pass

    return removed


# ─── CLI ───

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Discussion Session Manager")
    subparsers = parser.add_subparsers(dest="command")

    # create
    create_parser = subparsers.add_parser("create", help="Create a new discussion session")
    create_parser.add_argument("--topic", required=True, help="Discussion topic")
    create_parser.add_argument("--leader", default="alpha", help="Leader agent")
    create_parser.add_argument("--participants", default="alpha,beta", help="Comma-separated participant list")
    create_parser.add_argument("--phase", default="general", help="Discussion phase")
    create_parser.add_argument("--max-rounds", type=int, default=3, help="Max rounds")
    create_parser.add_argument("--description", default="", help="Description")

    # list
    subparsers.add_parser("list", help="List all discussion sessions")

    # status
    status_parser = subparsers.add_parser("status", help="Show session status")
    status_parser.add_argument("session_id", help="Session ID")

    # cleanup
    cleanup_parser = subparsers.add_parser("cleanup", help="Remove old sessions")
    cleanup_parser.add_argument("--max-age", type=int, default=24, help="Max age in hours")

    args = parser.parse_args()

    if args.command == "create":
        participants = [p.strip() for p in args.participants.split(",")]
        disc = DiscussionSession(
            topic=args.topic,
            leader=args.leader,
            participants=participants,
            phase=args.phase,
            max_rounds=args.max_rounds,
            description=args.description,
        )
        disc.create()
        print(json.dumps({
            "session_id": disc.session_id,
            "session_dir": disc.session_dir,
            "leader": disc.leader,
            "participants": disc.participants,
            "phase": disc.phase,
            "max_rounds": disc.max_rounds,
        }, indent=2))

    elif args.command == "list":
        sessions = list_sessions()
        if not sessions:
            print("No discussion sessions found.")
        else:
            for s in sessions:
                status_emoji = {"completed": "✅", "in_progress": "🔄", "collecting": "📥", "cancelled": "❌"}.get(s.get("status", ""), "❓")
                print(f"{status_emoji} {s['session_id'][:40]} | {s.get('topic', '?')[:40]} | Round {s.get('current_round', 0)}/{s.get('max_rounds', '?')} | {s.get('status', '?')}")

    elif args.command == "status":
        disc = get_session(args.session_id)
        if disc:
            print(disc.summary())
        else:
            print(f"Session not found: {args.session_id}")

    elif args.command == "cleanup":
        removed = cleanup_old_sessions(args.max_age)
        print(f"Cleaned up {removed} old session(s).")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
