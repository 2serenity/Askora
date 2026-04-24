from fastapi import APIRouter
from redis import Redis
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.metrics_service import metrics_service

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@router.get("/health/ready")
def readiness() -> dict[str, object]:
    db_ok = False
    redis_ok = False
    db_error: str | None = None
    redis_error: str | None = None

    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)
    finally:
        db.close()

    try:
        redis_ok = bool(Redis.from_url(settings.redis_url, decode_responses=True).ping())
    except Exception as exc:
        redis_error = str(exc)

    status = "ok" if db_ok and redis_ok else "degraded"
    return {
        "status": status,
        "dependencies": {
            "database": {"ok": db_ok, "error": db_error},
            "redis": {"ok": redis_ok, "error": redis_error},
        },
    }


@router.get("/metrics")
def metrics_snapshot() -> dict:
    return metrics_service.snapshot()

