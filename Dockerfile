FROM python:3.11-slim

LABEL org.opencontainers.image.title="AgentBoard"
LABEL org.opencontainers.image.description="Standalone multi-project task board for human+AI collaboration"
LABEL org.opencontainers.image.source="https://github.com/ajianaz/agentboard"
LABEL org.opencontainers.image.license="Apache-2.0"

WORKDIR /app

# Copy application files (zero pip install — Python stdlib only)
COPY server.py config.py db.py auth.py ./
COPY api/ ./api/
COPY static/ ./static/

# Persistent data directory (DB + API key)
RUN mkdir -p /app/data

VOLUME ["/app/data"]

EXPOSE 8765

# Config via environment variables (override defaults):
#   AGENTBOARD_PORT      - Server port (default: 8765)
#   AGENTBOARD_HOST      - Bind address (default: 0.0.0.0)
#   AGENTBOARD_DB_PATH   - Database file path (default: agentboard.db)
#   AGENTBOARD_API_KEY   - API key (default: auto-generated, printed to stdout)
#   AGENTBOARD_API_KEY_FILE - API key file path
#   AGENTBOARD_CONFIG    - Path to agentboard.toml
CMD ["python", "server.py"]
