# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow

# Install system deps: tzdata for TZ handling, sqlite3 libs, and minimal locales
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
        tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create app user and dirs
RUN useradd -m -u 10001 appuser
WORKDIR /app
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /app/requirements.txt

# Copy source
COPY app /app/app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh && chown -R appuser:appuser /app

USER appuser

# No ports exposed (long polling)
ENV BOT_TOKEN= \
    DAILY_GOAL_DEFAULT=2000 \
    TZ=Europe/Moscow

VOLUME ["/app/data"]

ENTRYPOINT ["/app/entrypoint.sh"]