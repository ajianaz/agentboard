# ── AgentBoard Docker Management ──────────────────────────

.PHONY: dev-up dev-down dev-restart dev-logs dev-ps \
        prod-up prod-down prod-restart prod-logs prod-ps \
        ps pull

COMPOSE_DEV  = docker compose -f docker-compose.agentboard-dev.yml
COMPOSE_PROD = docker compose -f docker-compose.agentboard-prod.yml

# ── Dev ───────────────────────────────────────────────────

dev-up:
	$(COMPOSE_DEV) up -d

dev-down:
	$(COMPOSE_DEV) down

dev-restart:
	$(COMPOSE_DEV) restart

dev-logs:
	$(COMPOSE_DEV) logs -f --tail=100

# ── Prod ──────────────────────────────────────────────────

prod-up:
	$(COMPOSE_PROD) up -d

prod-down:
	$(COMPOSE_PROD) down

prod-restart:
	$(COMPOSE_PROD) restart

prod-logs:
	$(COMPOSE_PROD) logs -f --tail=100

# ── Utilities ─────────────────────────────────────────────

ps:
	docker compose ps

pull:
	docker pull ghcr.io/ajianaz/agentboard:latest
