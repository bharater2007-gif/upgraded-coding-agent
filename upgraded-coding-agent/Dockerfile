# Multi-stage production container for Upgraded Coding Agent
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install security updates and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt pyproject.toml /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir streamlit

# Copy application source code
COPY agent /app/agent
COPY sandbox /app/sandbox
COPY api /app/api
COPY ui /app/ui
COPY eval /app/eval
COPY tests /app/tests
COPY run.py /app/run.py
COPY pytest.ini /app/pytest.ini
COPY .env.example /app/.env.example

# Create isolated execution sandbox directory & unprivileged security user
RUN mkdir -p /app/.sandboxes /app/.pytest_cache && \
    useradd -u 1000 -m agentuser && \
    chown -R agentuser:agentuser /app

USER agentuser

EXPOSE 8000
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["python", "run.py"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
