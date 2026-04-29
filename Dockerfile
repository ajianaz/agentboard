FROM python:3.11-slim

WORKDIR /app

COPY server.py config.py db.py auth.py kpi_engine.py activity_logger.py onboard.py webhook.py ./
COPY api/ ./api/
COPY static/ ./static/
COPY tools/ ./tools/

# No pip install — Python stdlib only
# Data files (.db, .api_key, .env) come from bind mount at runtime

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=5s \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/')"

CMD ["python3", "server.py"]
