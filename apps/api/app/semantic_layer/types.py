from typing import Any

from pydantic import BaseModel, Field


class SemanticMetric(BaseModel):
    key: str
    label: str
    description: str
    sql: str
    synonyms: list[str] = Field(default_factory=list)
    allowed_roles: list[str] = Field(default_factory=list)


class SemanticDimension(BaseModel):
    key: str
    label: str
    sql: str
    synonyms: list[str] = Field(default_factory=list)
    kind: str = "category"
    grain: str | None = None
    allowed_roles: list[str] = Field(default_factory=list)


class SemanticFilter(BaseModel):
    key: str
    label: str
    field: str
    operators: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)


class SemanticJoin(BaseModel):
    key: str
    table: str
    alias: str
    on: str


class SemanticDataset(BaseModel):
    table: str
    alias: str
    default_time_field: str
    source_key: str = "default"
    joins: list[str] = Field(default_factory=list)


class SemanticCatalog(BaseModel):
    version: int
    base_dataset: str
    datasets: dict[str, SemanticDataset]
    metrics: dict[str, SemanticMetric]
    dimensions: dict[str, SemanticDimension]
    filters: dict[str, SemanticFilter]
    joins: dict[str, SemanticJoin]
    business_terms: dict[str, dict[str, str]]
    time_mappings: dict[str, dict[str, str]]


class TemplateCatalog(BaseModel):
    templates: list[dict[str, Any]]
