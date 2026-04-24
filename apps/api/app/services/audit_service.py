from __future__ import annotations

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.privacy import redact_payload
from app.models.audit import AuditLog
from app.repositories.audit import AuditRepository


class AuditService:
    def __init__(self, db: Session):
        self.repository = AuditRepository(db)

    def log(
        self,
        *,
        actor_user_id,
        event_type: str,
        status: str,
        question: str | None = None,
        sql_text: str | None = None,
        blocked_reason: str | None = None,
        row_count: int = 0,
        interpretation_json: dict | None = None,
        validation_json: dict | None = None,
        extra_json: dict | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            event_type=event_type,
            status=status,
            question=question,
            sql_text=sql_text,
            blocked_reason=blocked_reason,
            row_count=row_count,
            interpretation_json=redact_payload(jsonable_encoder(interpretation_json or {})),
            validation_json=redact_payload(jsonable_encoder(validation_json or {})),
            extra_json=redact_payload(jsonable_encoder(extra_json or {})),
        )
        return self.repository.create(entry)

    def list_recent(self) -> list[AuditLog]:
        return self.repository.list_recent()

