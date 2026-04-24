from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    label: str
    start_date: date
    end_date: date
    grain: Literal["day", "week", "month", "hour"] = "day"


class ComparisonSpec(BaseModel):
    enabled: bool = False
    mode: Literal["previous_period", "year_over_year", "none"] = "none"
    baseline_label: str | None = None
    baseline_start_date: date | None = None
    baseline_end_date: date | None = None


class MultiDateSpec(BaseModel):
    dates: list[date] = Field(default_factory=list)
    mode: Literal["include"] = "include"


class ResolvedMetric(BaseModel):
    key: str
    label: str
    description: str
    expression: str


class ResolvedDimension(BaseModel):
    key: str
    label: str
    expression: str
    grain: str | None = None


class ResolvedFilter(BaseModel):
    key: str
    label: str
    operator: str
    value: Any


class QueryIntent(BaseModel):
    question: str
    intent_type: Literal["aggregation", "comparison", "trend", "table", "unknown"] = "unknown"
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    time_expression: str | None = None
    time_range_override: TimeRange | None = None
    multi_date: MultiDateSpec | None = None
    comparison: ComparisonSpec = Field(default_factory=ComparisonSpec)
    preferred_chart_type: Literal["line", "bar", "pie", "area", "kpi", "table"] | None = None
    sort: str | None = None
    limit: int | None = None
    confidence: float = 0.0
    ambiguity_reasons: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    question: str
    dataset: str
    intent_type: str
    metrics: list[ResolvedMetric]
    dimensions: list[ResolvedDimension]
    filters: list[ResolvedFilter]
    time_range: TimeRange
    multi_date: MultiDateSpec | None = None
    comparison: ComparisonSpec = Field(default_factory=ComparisonSpec)
    preferred_chart_type: Literal["line", "bar", "pie", "area", "kpi", "table"] | None = None
    sort: str | None = None
    limit: int = 50
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)


class VisualizationSpec(BaseModel):
    chart_type: Literal["line", "bar", "pie", "area", "kpi", "table"]
    x_key: str | None = None
    y_keys: list[str] = Field(default_factory=list)
    title: str
    description: str


class ValidationResult(BaseModel):
    allowed: bool
    normalized_sql: str
    complexity_score: int
    row_limit_applied: int
    estimated_cost: float | None = None
    estimated_rows: float | None = None
    explain_plan_json: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    dry_run: bool = False
    execution_context: Literal["interactive", "schedule"] = "interactive"


class QueryResult(BaseModel):
    question: str
    query_plan: QueryPlan
    generated_sql: str
    validation: ValidationResult
    visualization: VisualizationSpec
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    status: Literal["executed", "blocked", "needs_clarification", "failed"]
    user_message: str
    suggestions: list[str] = Field(default_factory=list)
    comparison_summary: dict[str, Any] | None = None
    processing_trace: dict[str, Any] | None = None


class QueryHistoryItem(BaseModel):
    id: UUID
    question: str
    status: str
    confidence: float
    chart_type: str | None
    row_count: int
    created_at: datetime
    sql_text: str
    result_preview_json: dict[str, Any]


class QueryExampleCreateRequest(BaseModel):
    text: str = Field(min_length=3, max_length=1000)
    is_pinned: bool = False


class QueryExampleSummary(BaseModel):
    id: UUID
    text: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime


class QueryTemplateSummary(BaseModel):
    name: str
    description: str
    example_question: str
    pattern: str
    guidance: str
    output_shape_json: dict[str, Any] = Field(default_factory=dict)
