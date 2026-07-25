"""
The AI Guards — FastAPI Application Entrypoint
Run dev:  uvicorn main:app --reload --port 8000
Run prod: uvicorn main:app --host 0.0.0.0 --port 8000 --workers $WEB_CONCURRENCY
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from database import init_db
from rate_limit import limiter
from routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("the_ai_guards")

ENV = os.getenv("ENV", "development").lower()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("The AI Guards API starting (env=%s)", ENV)
    if ENV == "production":
        logger.info("Production mode: expecting Alembic migrations to have run before startup.")
    else:
        logger.info("Development mode: initialising missing local database tables.")
        await init_db()
        logger.info("Database ready.")
    yield
    logger.info("The AI Guards API shutting down.")


# ── Allowed origins: set ALLOWED_ORIGINS in .env (comma-separated) ──────────
# Example: ALLOWED_ORIGINS=https://the-ai-guards.yourdomain.com,https://www.yourdomain.com
#
# FIX: a bare "*" combined with allow_credentials=True is both insecure and
# non-functional per the Fetch spec (browsers reject it). Rather than silently
# opening CORS to everyone, an unset/"*" value now collapses to an empty
# allow-list (same-origin only) and, in production, refuses to boot — forcing
# the operator to set explicit origins instead of accidentally deploying wide
# open.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "").strip()
if not _raw_origins or _raw_origins == "*":
    if ENV == "production":
        raise RuntimeError(
            "ALLOWED_ORIGINS must be set to an explicit comma-separated list "
            "of origins in production (wildcard CORS is not supported)."
        )
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    logger.warning(
        "ALLOWED_ORIGINS not set — allowing common Vite dev origins: %s",
        ALLOWED_ORIGINS,
    )
else:
    ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(
    title       = "The AI Guards Cloud API",
    description = "Edge-to-Cloud fall & bed-exit detection SaaS — multi-tenant",
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/docs" if ENV != "production" else None,
    redoc_url   = "/redoc" if ENV != "production" else None,
)

# ── Rate limiting (per-IP by default; per-route overrides live in routes.py) ─
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Baseline security headers ────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if ENV == "production":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Compress dashboard/aggregation JSON responses.
app.add_middleware(GZipMiddleware, minimum_size=512)

# Keep CORS outermost so even error responses during local development include
# the browser headers needed by the Vite frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "the-ai-guards-api"}
