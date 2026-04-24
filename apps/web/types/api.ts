export type UserSummary = {
  id: string;
  full_name: string;
  email: string;
  role: "admin" | "analyst" | "business_user";
  is_active: boolean;
  timezone: string;
  locale: string;
  created_at: string;
};

export type AuthResponse = {
  user: UserSummary;
};

export type MessageResponse = {
  message: string;
};

export type ComparisonSpec = {
  enabled: boolean;
  mode: string;
  baseline_label?: string | null;
  baseline_start_date?: string | null;
  baseline_end_date?: string | null;
};

export type QueryPlan = {
  question: string;
  dataset: string;
  intent_type: string;
  metrics: { key: string; label: string; description: string; expression: string }[];
  dimensions: { key: string; label: string; expression: string; grain?: string | null }[];
  filters: { key: string; label: string; operator: string; value: unknown }[];
  time_range: { label: string; start_date: string; end_date: string; grain: string };
  comparison: ComparisonSpec;
  preferred_chart_type?: "line" | "bar" | "pie" | "area" | "kpi" | "table" | null;
  sort?: string | null;
  limit: number;
  confidence: number;
  warnings: string[];
  needs_clarification: boolean;
  clarification_questions: string[];
};

export type ValidationResult = {
  allowed: boolean;
  normalized_sql: string;
  complexity_score: number;
  row_limit_applied: number;
  estimated_cost?: number | null;
  estimated_rows?: number | null;
  explain_plan_json?: Record<string, unknown> | null;
  warnings: string[];
  blocked_reasons: string[];
};

export type VisualizationSpec = {
  chart_type: "line" | "bar" | "pie" | "area" | "kpi" | "table";
  x_key?: string | null;
  y_keys: string[];
  title: string;
  description: string;
};

export type QueryRequest = {
  question: string;
  dry_run?: boolean;
  execution_context?: "interactive" | "schedule";
};

export type QueryResult = {
  question: string;
  query_plan: QueryPlan;
  generated_sql: string;
  validation: ValidationResult;
  visualization: VisualizationSpec;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  status: "executed" | "blocked" | "needs_clarification" | "failed";
  user_message: string;
  suggestions: string[];
  comparison_summary?: {
    items: { label: string; current: number; previous: number; delta: number; delta_pct?: number | null }[];
    metric: string;
  } | null;
  processing_trace?: Record<string, unknown> | null;
};

export type QueryHistoryItem = {
  id: string;
  question: string;
  status: string;
  confidence: number;
  chart_type?: string | null;
  row_count: number;
  created_at: string;
  sql_text: string;
  result_preview_json: Record<string, unknown>;
};

export type QueryExampleSummary = {
  id: string;
  text: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
};

export type QueryTemplateSummary = {
  name: string;
  description: string;
  example_question: string;
  pattern: string;
  guidance: string;
  output_shape_json: Record<string, unknown>;
};

export type SaveReportRequest = {
  name: string;
  description?: string | null;
  question: string;
  query_plan_json: Record<string, unknown>;
  sql_text: string;
  chart_type?: string | null;
  row_count?: number;
  result_preview_json?: Record<string, unknown>;
  execution_status?: string;
};

export type ReportSummary = {
  id: string;
  owner_id: string;
  name: string;
  description?: string | null;
  question: string;
  chart_type?: string | null;
  query_plan_json: Record<string, unknown>;
  last_run_status?: string | null;
  last_run_at?: string | null;
  last_run_row_count?: number | null;
  result_preview_json: Record<string, unknown>;
  runs_count: number;
  schedules_count: number;
  shares_count: number;
  created_at: string;
  updated_at: string;
};

export type ScheduleSummary = {
  id: string;
  report_id: string;
  cron_expression: string;
  timezone: string;
  recipient: string;
  channel: string;
  target_group_id?: string | null;
  is_active: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
};

export type ReportShareSummary = {
  id: string;
  group_id: string;
  group_name: string;
  shared_by_user_id: string;
  shared_by_name: string;
  note?: string | null;
  created_at: string;
};

export type ReportRunSummary = {
  id: string;
  trigger_source: string;
  status: string;
  row_count: number;
  executed_at: string;
  result_preview_json: Record<string, unknown>;
};

export type ReportDetail = ReportSummary & {
  query_plan_json: Record<string, unknown>;
  sql_text: string;
  schedules: ScheduleSummary[];
  runs: ReportRunSummary[];
  shares: ReportShareSummary[];
};

export type ScheduleRequest = {
  cron_expression: string;
  timezone: string;
  recipient?: string | null;
  channel: string;
  target_group_id?: string | null;
  is_active: boolean;
};

export type ProfileUpdateRequest = {
  full_name: string;
  timezone: string;
  locale: string;
};

export type PasswordChangeRequest = {
  current_password: string;
  new_password: string;
};

export type SemanticEntry = {
  id: string;
  term: string;
  entity_type: string;
  target_key: string;
  synonyms_json: string[];
  description?: string | null;
  is_active: boolean;
  created_at: string;
};

export type TemplateItem = {
  id: string;
  name: string;
  description: string;
  pattern: string;
  guidance: string;
  example_question: string;
  output_shape_json: Record<string, unknown>;
  owner_role: string;
  is_active: boolean;
  created_at: string;
};

export type AuditLogItem = {
  id: string;
  event_type: string;
  status: string;
  question?: string | null;
  blocked_reason?: string | null;
  sql_text?: string | null;
  row_count: number;
  created_at: string;
  interpretation_json: Record<string, unknown>;
  validation_json: Record<string, unknown>;
  extra_json: Record<string, unknown>;
};

export type CreateUserRequest = {
  email: string;
  full_name: string;
  password: string;
  role: "admin" | "analyst" | "business_user";
  is_active: boolean;
};

export type DataSourceSummary = {
  id: string;
  key: string;
  name: string;
  description?: string | null;
  dialect: string;
  connection_url: string;
  schema_name?: string | null;
  is_active: boolean;
  is_default: boolean;
  allowed_roles_json: string[];
  capabilities_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CsvColumnProfile = {
  name: string;
  inferred_type: string;
  non_null_ratio: number;
  unique_ratio: number;
};

export type CsvAutoCatalogPreview = {
  columns: CsvColumnProfile[];
  metrics_count: number;
  dimensions_count: number;
  filters_count: number;
  base_dataset: string;
};

export type CsvAutoResolutionCandidate = {
  source_key: string;
  table_name: string;
  confidence: number;
  reason: string;
};

export type CsvAutoResolution = {
  strategy: string;
  resolved_source_key: string;
  resolved_table_name: string;
  notes: string[];
  validated: boolean;
  validation_message?: string | null;
  candidates: CsvAutoResolutionCandidate[];
};

export type CsvAutoConfigResult = {
  applied: boolean;
  used_delimiter: string;
  catalog_preview: CsvAutoCatalogPreview;
  catalog?: Record<string, unknown> | null;
  auto_resolution: CsvAutoResolution;
};

export type GroupSummary = {
  id: string;
  name: string;
  description?: string | null;
  is_private: boolean;
  created_at: string;
  updated_at: string;
  member_count: number;
  current_user_role?: string | null;
};

export type GroupMemberSummary = {
  id: string;
  user_id: string;
  role: string;
  full_name: string;
  email: string;
  joined_at: string;
};

export type GroupMessageSummary = {
  id: string;
  author_user_id: string;
  author_name: string;
  body: string;
  payload_json: Record<string, unknown>;
  created_at: string;
};

export type GroupSharedReportSummary = {
  id: string;
  report_id: string;
  report_name: string;
  report_description?: string | null;
  report_question: string;
  chart_type?: string | null;
  owner_name: string;
  shared_by_name: string;
  metric_labels: string[];
  period_label?: string | null;
  last_run_status?: string | null;
  last_run_at?: string | null;
  last_run_row_count?: number | null;
  preview_json: Record<string, unknown>;
  query_plan_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type GroupDetail = GroupSummary & {
  members: GroupMemberSummary[];
  messages: GroupMessageSummary[];
  shared_reports: GroupSharedReportSummary[];
};
