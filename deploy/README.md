# Deployment

Production-ready Docker Compose files for AgentBoard.

## Quick Start (Production)

```bash
git clone https://github.com/ajianaz/agentboard.git
cd agentboard
cp .env.example .env
# Edit .env — set AGENTBOARD_DOMAIN, AGENTBOARD_API_KEY
docker compose -f deploy/docker-compose.prod.yml up -d
```

## Development/Staging

Run a second instance alongside production:

```bash
git clone https://github.com/ajianaz/agentboard.git agentboard-dev
cd agentboard-dev
cp .env.example .env
# Edit .env — set AGENTBOARD_DEV_DOMAIN
docker compose -p agentboard-dev -f deploy/docker-compose.dev.yml up -d
```

## How It Works

- **Single Docker image** (`ghcr.io/ajianaz/agentboard:latest`) — no rebuild for code changes
- **Bind mount** (`./:/app`) — `git pull` reflects immediately in the running container
- **SQLite database** (`agentboard.db`) — stored in the mounted directory, survives restarts
- **API key** (`.api_key`) — auto-generated on first run, stored in mounted directory

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTBOARD_DOMAIN` | `board.example.com` | Public domain for production |
| `AGENTBOARD_DEV_DOMAIN` | `dev.board.example.com` | Public domain for dev/staging |
| `AGENTBOARD_PORT` | `8765` | Internal HTTP port |
| `AGENTBOARD_PUBLIC_READ` | `true` | Allow unauthenticated GET requests |
| `AGENTBOARD_DATA_DIR` | `.` (repo root) | Host directory to bind mount |
| `TRAEFIK_NETWORK` | `public-net` | Docker network for Traefik |
| `TRAEFIK_CERT_RESOLVER` | `myresolver` | Traefik TLS cert resolver name |
| `TZ` | `Asia/Jakarta` | Server timezone |

## Hermes Deployment (Reference)

The Hermes fleet uses these paths:

| Instance | Host Path | Domain | Port | Compose File |
|----------|-----------|--------|------|--------------|
| Production | `/opt/data/agentboard/` | `company.ajianaz.dev` | 8765 | `docker-compose.agentboard-prod.yml` (host) |
| Development | `/opt/data/agentboard-dev/` | `board.ajianaz.dev` | 8766 | `docker-compose.agentboard-dev.yml` (host) |

Host compose files live outside the repo at `/opt/data/docker-compose.agentboard-*.yml` with hardcoded paths.
