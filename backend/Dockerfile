FROM python:3.11-slim

WORKDIR /app

# System deps for asyncpg/bcrypt wheels + curl for the HEALTHCHECK.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# FIX: previously ran as root inside the container. Create an unprivileged
# user and drop to it before serving traffic.
RUN useradd --create-home --uid 1000 appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# FIX: add a container-level healthcheck so orchestrators (Docker/K8s/Render)
# can detect a hung or crash-looping app instead of relying only on the
# process staying alive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run Alembic before serving so Render/Supabase deployments apply schema
# changes deterministically instead of relying on SQLAlchemy create_all().
ENV WEB_CONCURRENCY=4
CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY}"]
