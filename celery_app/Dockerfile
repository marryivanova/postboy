FROM python:3.12.3-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir poetry==1.7.1

COPY pyproject.toml poetry.lock* ./

RUN --mount=type=cache,target=/root/.cache/pypoetry \
    poetry config virtualenvs.create false && \
    poetry source add pypi https://pypi.org/simple/ --priority=primary 2>/dev/null || true && \
    poetry install --only main --no-interaction --no-ansi --no-root

COPY . .

RUN poetry install --only main --no-interaction --no-ansi

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD celery -A celery_app inspect ping || exit 1


ENV TZ=Europe/Moscow \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["celery", "-A", "src.app_celery.celery_app", "worker", "--loglevel=info", "--concurrency=4"]