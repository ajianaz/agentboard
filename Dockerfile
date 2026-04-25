FROM python:3.11-slim

WORKDIR /opt/data/agentboard

COPY server.py config.py db.py auth.py ./
COPY api/ ./api/
COPY static/ ./static/

RUN mkdir -p /opt/data/agentboard/data

EXPOSE 8765

CMD ["python3", "server.py"]
