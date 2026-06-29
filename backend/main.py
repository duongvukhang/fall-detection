"""
SafeWatch — FastAPI Application Entrypoint
Run dev:  uvicorn main:app --reload --port 8000
Run prod: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import init_db
from routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("safewatch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SafeWatch API starting — initialising database …")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("SafeWatch API shutting down.")


# ── Allowed origins: set ALLOWED_ORIGINS in .env (comma-separated) ──────────
# Example: ALLOWED_ORIGINS=https://safewatch.yourdomain.com,https://www.yourdomain.com
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",")]

app = FastAPI(
    title       = "SafeWatch Cloud API",
    description = "Edge-to-Cloud fall & bed-exit detection SaaS — multi-tenant",
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

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
    return {"status": "ok", "service": "safewatch-api"}