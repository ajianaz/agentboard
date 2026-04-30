# GitHub Actions — Track Agent Runs in AgentBoard

Post agent session lifecycle events to AgentBoard's webhook endpoint.
Works with any AI agent framework that runs in CI/CD.

## Setup

1. **AgentBoard server** must be running and accessible from GitHub Actions
2. **Repository secrets** required:
   - `AGENTBOARD_URL` — e.g. `https://board.example.com` or `http://your-server:8765`
   - `AGENTBOARD_API_KEY` — API key from AgentBoard setup

## Usage

### Option 1: Composite Action (recommended)

```yaml
# .github/workflows/agent-tracker.yml
name: Agent Tracker

on:
  workflow_run:
    workflows: ["*"]
    types: [completed]

jobs:
  track:
    runs-on: ubuntu-latest
    if: github.event.workflow_run.conclusion != 'skipped'
    steps:
      - uses: ajianaz/agentboard/.github/actions/agent-track@develop
        with:
          agent-id: "github-actions"
          event-type: "session_end"
          session-id: "${{ github.event.workflow_run.id }}"
          message: "${{ github.event.workflow_run.name }} — ${{ github.event.workflow_run.conclusion }}"
          board-url: ${{ secrets.AGENTBOARD_URL }}
          board-key: ${{ secrets.AGENTBOARD_API_KEY }}
```

### Option 2: Inline curl (no action dependency)

```yaml
# .github/workflows/ai-agent.yml
name: AI Agent Pipeline

on:
  issues:
    types: [labeled]

jobs:
  run-agent:
    runs-on: ubuntu-latest
    if: contains(github.event.label.name, 'agent-task')
    steps:
      # 1. Notify start
      - name: Track session start
        run: |
          curl -sf -X POST "${{ secrets.AGENTBOARD_URL }}/api/webhook/agent-event" \
            -H "Authorization: Bearer ${{ secrets.AGENTBOARD_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{
              "agent_id": "github-agent",
              "event_type": "session_start",
              "session_id": "gh-${{ github.run_id }}",
              "message": "Processing #${{ github.event.issue.number }}: ${{ github.event.issue.title }}"
            }'

      # 2. Your agent work here
      - name: Run agent
        run: |
          echo "Doing agent work for issue #${{ github.event.issue.number }}..."
          # python my_agent.py --issue ${{ github.event.issue.number }}

      # 3. Notify completion
      - name: Track session end
        if: always()
        run: |
          curl -sf -X POST "${{ secrets.AGENTBOARD_URL }}/api/webhook/agent-event" \
            -H "Authorization: Bearer ${{ secrets.AGENTBOARD_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{
              "agent_id": "github-agent",
              "event_type": "session_end",
              "session_id": "gh-${{ github.run_id }}"
            }'
```

### Option 3: Multi-step task tracking

```yaml
name: Multi-Step Agent

on: [workflow_dispatch]

jobs:
  pipeline:
    runs-on: ubuntu-latest
    env:
      BOARD_URL: ${{ secrets.AGENTBOARD_URL }}
      BOARD_KEY: ${{ secrets.AGENTBOARD_API_KEY }}
      SESSION: "gh-${{ github.run_id }}"

    steps:
      - uses: actions/checkout@v4

      - name: Step 1 — Research
        run: |
          curl -sf -X POST "$BOARD_URL/api/webhook/agent-event" \
            -H "Authorization: Bearer $BOARD_KEY" -H "Content-Type: application/json" \
            -d "{\"agent_id\":\"research\",\"event_type\":\"task_start\",\"session_id\":\"$SESSION-research\",\"message\":\"Research phase\"}"
          # ... research work ...
          curl -sf -X POST "$BOARD_URL/api/webhook/agent-event" \
            -H "Authorization: Bearer $BOARD_KEY" -H "Content-Type: application/json" \
            -d "{\"agent_id\":\"research\",\"event_type\":\"task_end\",\"session_id\":\"$SESSION-research\"}"

      - name: Step 2 — Implement
        run: |
          curl -sf -X POST "$BOARD_URL/api/webhook/agent-event" \
            -H "Authorization: Bearer $BOARD_KEY" -H "Content-Type: application/json" \
            -d "{\"agent_id\":\"dev\",\"event_type\":\"task_start\",\"session_id\":\"$SESSION-implement\",\"message\":\"Implementation phase\"}"
          # ... implementation work ...
          curl -sf -X POST "$BOARD_URL/api/webhook/agent-event" \
            -H "Authorization: Bearer $BOARD_KEY" -H "Content-Type: application/json" \
            -d "{\"agent_id\":\"dev\",\"event_type\":\"task_end\",\"session_id\":\"$SESSION-implement\"}"

      - name: Step 3 — Review
        if: always()
        run: |
          curl -sf -X POST "$BOARD_URL/api/webhook/agent-event" \
            -H "Authorization: Bearer $BOARD_KEY" -H "Content-Type: application/json" \
            -d "{\"agent_id\":\"reviewer\",\"event_type\":\"task_start\",\"session_id\":\"$SESSION-review\",\"message\":\"Review phase\"}"
          # ... review work ...
          curl -sf -X POST "$BOARD_URL/api/webhook/agent-event" \
            -H "Authorization: Bearer $BOARD_KEY" -H "Content-Type: application/json" \
            -d "{\"agent_id\":\"reviewer\",\"event_type\":\"task_end\",\"session_id\":\"$SESSION-review\"}"
```

## Advanced: Custom Project Routing

Add `agent_id` values that match your `agentboard.toml` `[agents]` mapping:

```yaml
# agentboard.toml
[agents]
github-agent = "ci-cd"
research = "research"
dev = "development"
reviewer = "code-review"
```

## Environment Variables vs Secrets

| Variable | Use Secrets | Notes |
|----------|-------------|-------|
| `AGENTBOARD_URL` | ✅ | Don't expose internal URLs in logs |
| `AGENTBOARD_API_KEY` | ✅ | Required for write operations |
| `AGENTBOARD_AGENT_ID` | ❌ Optional | Override default agent identifier |
