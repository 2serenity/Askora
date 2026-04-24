from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SemanticEntryRequest(BaseModel):
    term: str = Field(min_length=2, max_length=255)
    entity_type: str = Field(min_length=2, max_length=50)
    target_key: str = Field(min_length=2, max_length=120)
    synonyms_json: list[str] = Field(default_factory=list)
    description: str | None = None
    is_active: bool = True


class SemanticEntrySummary(SemanticEntryRequest):
    id: UUID
    created_at: datetime


class TemplateRequest(BaseModel):
    name: str
    description: str
    pattern: str
    guidance: str
    example_question: str
    output_shape_json: dict[str, Any]
    owner_role: str
    is_active: bool = True


class TemplateSummary(TemplateRequest):
    id: UUID
    created_at: datetime


class RoleUpdateRequest(BaseModel):
    role: str


class AuditLogSummary(BaseModel):
    id: UUID
    event_type: str
    status: str
    question: str | None
    blocked_reason: str | None
    sql_text: str | None = None
    row_count: int
    created_at: datetime
    interpretation_json: dict[str, Any]
    validation_json: dict[str, Any]
    extra_json: dict[str, Any] = Field(default_factory=dict)


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    full_name: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    role: str = Field(default="business_user")
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Введите корректный email")
        return normalized


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class DataSourceRequest(BaseModel):
    key: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    dialect: str = Field(min_length=2, max_length=40)
    connection_url: str = Field(min_length=5, max_length=2000)
    schema_name: str | None = Field(default=None, max_length=120)
    is_active: bool = True
    is_default: bool = False
    allowed_roles_json: list[str] = Field(default_factory=list)
    capabilities_json: dict[str, Any] = Field(default_factory=dict)


class DataSourceSummary(DataSourceRequest):
    id: UUID
    created_at: datetime
    updated_at: datetime


class CsvColumnProfile(BaseModel):
    name: str
    inferred_type: str
    non_null_ratio: float
    unique_ratio: float


class CsvAutoCatalogPreview(BaseModel):
    columns: list[CsvColumnProfile]
    metrics_count: int
    dimensions_count: int
    filters_count: int
    base_dataset: str


class CsvAutoResolutionCandidate(BaseModel):
    source_key: str
    table_name: str
    confidence: float
    reason: str


class CsvAutoResolution(BaseModel):
    strategy: str
    resolved_source_key: str
    resolved_table_name: str
    notes: list[str] = Field(default_factory=list)
    validated: bool = True
    validation_message: str | None = None
    candidates: list[CsvAutoResolutionCandidate] = Field(default_factory=list)


class CsvAutoConfigResponse(BaseModel):
    applied: bool
    used_delimiter: str
    catalog_preview: CsvAutoCatalogPreview
    catalog: dict[str, Any] | None = None
    auto_resolution: CsvAutoResolution
