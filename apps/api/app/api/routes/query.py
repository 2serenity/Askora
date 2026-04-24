from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.query import (
    QueryExampleCreateRequest,
    QueryExampleSummary,
    QueryHistoryItem,
    QueryRequest,
    QueryResult,
    QueryTemplateSummary,
)
from app.semantic_layer.loader import semantic_loader
from app.services.query_service import QueryService
from app.services.rate_limit_service import query_rate_limiter
from app.services.metrics_service import metrics_service

router = APIRouter()


@router.post("/run", response_model=QueryResult)
def run_query(
    payload: QueryRequest,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryResult:
    decision = query_rate_limiter.check(f"{user.id}:query_run")
    response.headers["X-RateLimit-Limit"] = str(decision.limit)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    if not decision.allowed:
        metrics_service.observe_rate_limit_block()
        response.headers["Retry-After"] = str(decision.retry_after_seconds)
        raise HTTPException(
            status_code=429,
            detail=(
                "Слишком много запросов за короткое время. "
                f"Лимит: {decision.limit} за окно. Повторите через {decision.retry_after_seconds} сек."
            ),
        )
    return QueryService(db).run(payload, user)


@router.get("/history", response_model=list[QueryHistoryItem])
def list_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[QueryHistoryItem]:
    items = QueryService(db).list_history(user)
    return [QueryHistoryItem.model_validate(item, from_attributes=True) for item in items]


@router.delete("/history/{history_id}", response_model=MessageResponse)
def delete_history_item(
    history_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    deleted = QueryService(db).delete_history_item(history_id, user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Запись истории не найдена")
    return MessageResponse(message="Запись из истории удалена")


@router.delete("/history", response_model=MessageResponse)
def clear_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> MessageResponse:
    deleted = QueryService(db).clear_history(user)
    return MessageResponse(message=f"История очищена. Удалено записей: {deleted}")


@router.get("/examples", response_model=list[QueryExampleSummary])
def list_examples(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[QueryExampleSummary]:
    items = QueryService(db).list_examples(user)
    return [QueryExampleSummary.model_validate(item, from_attributes=True) for item in items]


@router.get("/templates", response_model=list[QueryTemplateSummary])
def list_templates(user: User = Depends(get_current_user)) -> list[QueryTemplateSummary]:
    _ = user
    templates = semantic_loader.load_templates()
    response: list[QueryTemplateSummary] = []
    for item in templates.templates:
        response.append(
            QueryTemplateSummary(
                name=item.get("name", ""),
                description=item.get("description", ""),
                example_question=item.get("example_question", ""),
                pattern=item.get("pattern", ""),
                guidance=item.get("guidance", ""),
                output_shape_json=item.get("output_shape", {}) or {},
            )
        )
    return response


@router.post("/examples", response_model=QueryExampleSummary)
def create_example(
    payload: QueryExampleCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> QueryExampleSummary:
    item = QueryService(db).create_example(payload, user)
    return QueryExampleSummary.model_validate(item, from_attributes=True)


@router.delete("/examples/{example_id}", response_model=MessageResponse)
def delete_example(example_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> MessageResponse:
    deleted = QueryService(db).delete_example(example_id, user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Пример не найден")
    return MessageResponse(message="Пример удалён")
