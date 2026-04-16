"""FastAPI application entry point.

Creates the FastAPI app, registers routers, adds CORS and auth middleware,
configures Prometheus instrumentation, and sets up startup/shutdown events
for the DB pool and background tasks (idle checker, expiry job).

Validates: Requirements 1.1, 10.4, 11.1
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.images import router as images_router
from app.api.memory import router as memory_router
from app.core.auth import jwt_validator
from app.core.config import settings
from app.models.database import engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Background task references (populated on startup, cancelled on shutdown)
# ---------------------------------------------------------------------------
_background_tasks: list[asyncio.Task] = []


async def _idle_checker_loop() -> None:
    """Periodically check for idle conversations and generate summaries.

    Runs every 60 seconds. Finds conversations idle >= 5 minutes and
    triggers summary generation + email for each.
    """
    from app.models.database import async_session_factory
    from app.services.bedrock import BedrockService
    from app.services.session import SessionManager

    while True:
        try:
            async with async_session_factory() as db:
                bedrock = BedrockService()
                manager = SessionManager(db=db, bedrock=bedrock)
                idle_ids = await manager.check_idle_conversations()
                for conv_id in idle_ids:
                    try:
                        await manager.generate_and_email_summary(conv_id)
                    except Exception:
                        logger.exception(
                            "Failed to process idle conversation %s", conv_id
                        )
        except Exception:
            logger.exception("Error in idle checker loop")

        await asyncio.sleep(60)


async def _expiry_job_loop() -> None:
    """Daily job: archive conversations older than 30 days.

    Runs once every 24 hours. Generates summaries for expired conversations,
    stores them in session_summaries, then deletes the originals.
    """
    from app.models.database import async_session_factory
    from app.services.bedrock import BedrockService
    from app.services.session import SessionManager

    while True:
        try:
            async with async_session_factory() as db:
                bedrock = BedrockService()
                manager = SessionManager(db=db, bedrock=bedrock)
                await manager.run_expiry_job()
        except Exception:
            logger.exception("Error in expiry job loop")

        await asyncio.sleep(86_400)  # 24 hours


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: DB pool verification and background tasks."""
    # --- Startup ---
    logger.info("Starting up — verifying DB pool connectivity")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("DB pool initialised successfully")
    except Exception:
        logger.exception("DB pool initialisation failed — app may be unhealthy")

    # Launch background tasks
    idle_task = asyncio.create_task(_idle_checker_loop(), name="idle-checker")
    expiry_task = asyncio.create_task(_expiry_job_loop(), name="expiry-job")
    _background_tasks.extend([idle_task, expiry_task])
    logger.info("Background tasks started: idle-checker, expiry-job")

    yield

    # --- Shutdown ---
    logger.info("Shutting down — cancelling background tasks")
    for task in _background_tasks:
        task.cancel()

    for task in _background_tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass

    _background_tasks.clear()

    logger.info("Disposing DB engine")
    await engine.dispose()
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth middleware — JWT validation on protected routes
# ---------------------------------------------------------------------------
# Public paths that do NOT require authentication.
_PUBLIC_PATHS: set[str] = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/health",
    "/metrics",
}
_PUBLIC_PREFIXES: tuple[str, ...] = (
    "/docs",
    "/redoc",
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next) -> Response:
    """Validate JWT on every request to protected endpoints.

    Public paths (health, metrics, docs) are excluded.
    Returns 401 for missing/invalid/expired tokens.
    Set env CLAUDE_SIM_SKIP_AUTH=true to bypass (dev mode).
    """
    import os
    if os.environ.get("CLAUDE_SIM_SKIP_AUTH", "").lower() == "true":
        return await call_next(request)

    path = request.url.path

    # Allow public endpoints through without auth
    if path in _PUBLIC_PATHS or path.startswith(_PUBLIC_PREFIXES):
        return await call_next(request)

    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing or invalid authorization header"},
        )

    try:
        jwt_validator.validate_token(token)
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or expired token"},
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(memory_router)
app.include_router(images_router)
app.include_router(health_router)

# ---------------------------------------------------------------------------
# Prometheus metrics at /metrics
# ---------------------------------------------------------------------------
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
