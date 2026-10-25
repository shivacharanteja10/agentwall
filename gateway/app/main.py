"""Main FastAPI application for AgentWall gateway."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from app.api import admin, gateway
from app.core.config import get_settings
from app.db.base import close_db, init_db
from app.services.rate_limiter import (
    get_egress_controller,
    get_loop_detector,
    get_rate_limiter,
)
from app.services.upstream_client import get_upstream_manager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    format="%(message)s",
    level=getattr(logging, settings.log_level.upper()),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()

    # Initialize services
    rate_limiter = await get_rate_limiter()
    egress_controller = await get_egress_controller()
    loop_detector = await get_loop_detector()

    # Initialize upstream manager
    upstream = get_upstream_manager()
    await upstream.initialize()

    yield

    # Shutdown
    await rate_limiter.close()
    if egress_controller._redis:
        await egress_controller._redis.close()
    if loop_detector._redis:
        await loop_detector._redis.close()
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Zero-trust security gateway for AI agent tool calls",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_request_time(request: Request, call_next):
    import time
    start = time.time()
    request.state.request_time = datetime.utcnow()
    response = await call_next(request)
    process_time = time.time() - start
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = structlog.get_logger()
    logger.exception("Unhandled exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Include routers
app.include_router(gateway.router, prefix="/api/v1")
app.include_router(admin.router)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/admin/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
