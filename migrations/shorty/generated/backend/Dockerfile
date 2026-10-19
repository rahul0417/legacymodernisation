# Slim runtime image for the Shorty FastAPI backend.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for asyncpg / psycopg are not strictly needed (pure-python
# wheels exist), but keep `build-essential` available for any optional libs
# that might be added later. Strip to a minimum to keep the image small.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
RUN pip install --upgrade pip \
    && pip install \
        "fastapi==0.110.0" \
        "uvicorn[standard]==0.27.0" \
        "sqlalchemy[asyncio]==2.0.27" \
        "asyncpg==0.29.0" \
        "pydantic==2.6.0" \
        "pydantic-settings==2.1.0" \
        "alembic==1.13.1"

COPY app /app/app
COPY alembic.ini /app/alembic.ini

EXPOSE 8000

# Run Alembic before starting uvicorn (idempotent — `alembic upgrade head`).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
