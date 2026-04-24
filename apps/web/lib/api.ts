import type {
  CreateUserRequest,
  DataSourceSummary,
  CsvAutoConfigResult,
  AuthResponse,
  PasswordChangeRequest,
  ProfileUpdateRequest,
  QueryHistoryItem,
  QueryExampleSummary,
  QueryTemplateSummary,
  QueryRequest,
  QueryResult,
  ReportDetail,
  ReportSummary,
  SaveReportRequest,
  ScheduleRequest,
  ScheduleSummary,
  SemanticEntry,
  TemplateItem,
  UserSummary,
  AuditLogItem,
  GroupDetail,
  GroupSummary,
  GroupMessageSummary,
  MessageResponse,
} from "@/types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = "Ошибка запроса";
    try {
      const payload = await response.json();
      const detail = payload.detail ?? payload.message;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((item) => {
            if (typeof item === "string") return item;
            if (item?.msg) return item.msg;
            return JSON.stringify(item);
          })
          .join("; ");
      } else if (detail && typeof detail === "object") {
        message = detail.message ?? JSON.stringify(detail);
      }
    } catch {
      message = response.statusText;
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  login: (body: { email: string; password: string }) =>
    apiFetch<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  register: (body: { email: string; password: string; full_name: string }) =>
    apiFetch<AuthResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  logout: () => apiFetch<{ message: string }>("/auth/logout", { method: "POST" }),
  me: () => apiFetch<AuthResponse>("/auth/me"),
  updateProfile: (body: ProfileUpdateRequest) =>
    apiFetch<AuthResponse>("/auth/me", { method: "PUT", body: JSON.stringify(body) }),
  changePassword: (body: PasswordChangeRequest) =>
    apiFetch<MessageResponse>("/auth/me/password", { method: "PUT", body: JSON.stringify(body) }),
  runQuery: (body: QueryRequest) =>
    apiFetch<QueryResult>("/query/run", { method: "POST", body: JSON.stringify(body) }),
  queryHistory: () => apiFetch<QueryHistoryItem[]>("/query/history"),
  queryExamples: () => apiFetch<QueryExampleSummary[]>("/query/examples"),
  queryTemplates: () => apiFetch<QueryTemplateSummary[]>("/query/templates"),
  createQueryExample: (body: { text: string; is_pinned?: boolean }) =>
    apiFetch<QueryExampleSummary>("/query/examples", { method: "POST", body: JSON.stringify(body) }),
  deleteQueryExample: (id: string) => apiFetch<MessageResponse>(`/query/examples/${id}`, { method: "DELETE" }),
  deleteHistoryItem: (id: string) => apiFetch<MessageResponse>(`/query/history/${id}`, { method: "DELETE" }),
  clearHistory: () => apiFetch<MessageResponse>("/query/history", { method: "DELETE" }),
  reports: () => apiFetch<ReportSummary[]>("/reports"),
  sharedReports: () => apiFetch<ReportSummary[]>("/reports/shared"),
  report: (id: string) => apiFetch<ReportDetail>(`/reports/${id}`),
  rerunReport: (id: string) => apiFetch<QueryResult>(`/reports/${id}/rerun`, { method: "POST" }),
  deleteReport: (id: string) => apiFetch<MessageResponse>(`/reports/${id}`, { method: "DELETE" }),
  saveReport: (body: SaveReportRequest) =>
    apiFetch<ReportSummary>("/reports", { method: "POST", body: JSON.stringify(body) }),
  shareReportToGroup: (reportId: string, body: { group_id: string; note?: string }) =>
    apiFetch<MessageResponse>(`/reports/${reportId}/share/group`, { method: "POST", body: JSON.stringify(body) }),
  createSchedule: (reportId: string, body: ScheduleRequest) =>
    apiFetch<ScheduleSummary>(`/schedules/report/${reportId}`, { method: "POST", body: JSON.stringify(body) }),
  schedules: () => apiFetch<ScheduleSummary[]>("/schedules"),
  deleteSchedule: (id: string) => apiFetch<MessageResponse>(`/schedules/${id}`, { method: "DELETE" }),
  adminUsers: () => apiFetch<UserSummary[]>("/admin/users"),
  createAdminUser: (body: CreateUserRequest) =>
    apiFetch<UserSummary>("/admin/users", { method: "POST", body: JSON.stringify(body) }),
  updateUserRole: (userId: string, role: string) =>
    apiFetch<UserSummary>(`/admin/users/${userId}/role`, {
      method: "PUT",
      body: JSON.stringify({ role })
    }),
  updateUserStatus: (userId: string, is_active: boolean) =>
    apiFetch<UserSummary>(`/admin/users/${userId}/status`, {
      method: "PUT",
      body: JSON.stringify({ is_active })
    }),
  semanticEntries: () => apiFetch<SemanticEntry[]>("/admin/semantic-entries"),
  createSemanticEntry: (body: Omit<SemanticEntry, "id" | "created_at">) =>
    apiFetch<SemanticEntry>("/admin/semantic-entries", { method: "POST", body: JSON.stringify(body) }),
  templates: () => apiFetch<TemplateItem[]>("/admin/templates"),
  createTemplate: (body: Omit<TemplateItem, "id" | "created_at">) =>
    apiFetch<TemplateItem>("/admin/templates", { method: "POST", body: JSON.stringify(body) }),
  auditLogs: () => apiFetch<AuditLogItem[]>("/admin/audit-logs"),
  dataSources: () => apiFetch<DataSourceSummary[]>("/admin/data-sources"),
  createDataSource: (body: Omit<DataSourceSummary, "id" | "created_at" | "updated_at">) =>
    apiFetch<DataSourceSummary>("/admin/data-sources", { method: "POST", body: JSON.stringify(body) }),
  updateDataSource: (id: string, body: Omit<DataSourceSummary, "id" | "created_at" | "updated_at">) =>
    apiFetch<DataSourceSummary>(`/admin/data-sources/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  autoConfigFromCsv: (body: FormData) =>
    apiFetch<CsvAutoConfigResult>("/admin/data-sources/auto-config/csv", { method: "POST", body }),
  groups: () => apiFetch<GroupSummary[]>("/groups"),
  group: (id: string) => apiFetch<GroupDetail>(`/groups/${id}`),
  createGroup: (body: { name: string; description?: string; is_private: boolean }) =>
    apiFetch<GroupDetail>("/groups", { method: "POST", body: JSON.stringify(body) }),
  updateGroup: (id: string, body: { name: string; description?: string; is_private: boolean }) =>
    apiFetch<GroupSummary>(`/groups/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteGroup: (id: string) => apiFetch<MessageResponse>(`/groups/${id}`, { method: "DELETE" }),
  groupUsers: () => apiFetch<UserSummary[]>("/groups/users/available"),
  saveGroupMember: (groupId: string, body: { user_id: string; role: string }) =>
    apiFetch<MessageResponse>(`/groups/${groupId}/members`, { method: "POST", body: JSON.stringify(body) }),
  deleteGroupMember: (groupId: string, userId: string) =>
    apiFetch<MessageResponse>(`/groups/${groupId}/members/${userId}`, { method: "DELETE" }),
  groupMessages: (groupId: string) => apiFetch<GroupMessageSummary[]>(`/groups/${groupId}/messages`),
  postGroupMessage: (groupId: string, body: { body: string }) =>
    apiFetch<GroupMessageSummary>(`/groups/${groupId}/messages`, { method: "POST", body: JSON.stringify(body) }),
};
