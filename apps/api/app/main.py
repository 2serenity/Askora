from contextlib import asynccontextmanager
from time import perf_counter
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from app.api.routes import admin, auth, groups, health, query, reports, schedules
from app.core.config import settings
from app.core.logging import configure_logging
import app.models  # noqa: F401
from app.services.metrics_service import metrics_service
from app.scheduler.runner import scheduler_runner

configure_logging()
settings.validate_production_safety()
http_logger = structlog.get_logger("http")


@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler_runner.start()
    yield
    scheduler_runner.stop()


app = FastAPI(
    title="Analytics Workspace API",
    version="0.1.0",
    description="Self-service analytics platform with semantic-layer-driven NL2SQL",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    start = perf_counter()
    response = None
    error_message: str | None = None
    try:
        response = await call_next(request)
    except Exception as exc:
        error_message = str(exc)
        raise
    finally:
        duration_ms = round((perf_counter() - start) * 1000, 2)
        status_code = response.status_code if response is not None else 500
        metrics_service.observe_http(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        http_logger.info(
            "http_request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
            error=error_message,
        )
        clear_contextvars()
    if response is not None:
        response.headers["X-Request-ID"] = request_id
        return response
    raise RuntimeError("Unexpected middleware state without response.")

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(query.router, prefix="/api/v1/query", tags=["query"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["schedules"])
app.include_router(groups.router, prefix="/api/v1/groups", tags=["groups"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
