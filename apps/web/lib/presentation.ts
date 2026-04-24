import type { QueryPlan } from "@/types/api";

export type MetricKind = "count" | "currency" | "rate" | "duration" | "distance" | "other";

const roleLabels: Record<string, string> = {
  admin: "Администратор",
  analyst: "Аналитик",
  business_user: "Пользователь",
  owner: "Владелец группы",
  manager: "Менеджер группы",
  member: "Участник группы",
  viewer: "Только просмотр",
};

const statusLabels: Record<string, string> = {
  executed: "Выполнен",
  blocked: "Заблокирован",
  needs_clarification: "Нужно уточнение",
  failed: "Ошибка",
  success: "Успешно",
  deduplicated: "Без дублей",
};

const chartTypeLabels: Record<string, string> = {
  line: "Линейный график",
  bar: "Столбчатый график",
  pie: "Круговая диаграмма",
  area: "Диаграмма площади",
  kpi: "Итоговые карточки",
  table: "Таблица",
};

const auditEventLabels: Record<string, string> = {
  query_interpreted: "Требуется уточнение",
  query_reconciled: "План запроса скорректирован",
  query_blocked: "Запрос заблокирован",
  query_executed: "Запрос выполнен",
  query_failed: "Ошибка выполнения",
  schedule_fired: "Сработало расписание",
  report_deleted: "Отчёт удалён",
  report_shared_to_group: "Отчёт опубликован в группе",
  schedule_deleted: "Расписание удалено",
  history_deleted: "Запись истории удалена",
  history_cleared: "История очищена",
  group_created: "Создана группа",
  group_updated: "Обновлена группа",
  group_deleted: "Удалена группа",
  group_member_added: "Добавлен участник",
  group_member_updated: "Обновлена роль участника",
  group_member_removed: "Удалён участник",
  group_message_posted: "Новое сообщение в группе",
  profile_updated: "Профиль обновлён",
  password_changed: "Пароль обновлён",
};

const channelLabels: Record<string, string> = {
  email: "Email",
  telegram: "Телеграм",
  vk: "ВКонтакте",
  inbox: "Внутренний канал",
  group: "Рабочая группа",
};

const analyticsValueLabels: Record<string, string> = {
  done: "Выполнен",
  cancel: "Отменён",
  decline: "Отклонён",
  created: "Создан",
  assigned: "Назначен",
  in_progress: "В поездке",
  unknown: "Не указано",
  table: "Таблица",
};

const metricKindByKey: Record<string, MetricKind> = {
  total_orders: "count",
  completed_orders: "count",
  cancelled_orders: "count",
  total_tenders: "count",
  successful_tenders: "count",
  declined_tenders: "count",
  client_cancellations: "count",
  driver_cancellations: "count",
  total_revenue: "currency",
  avg_order_price: "currency",
  tender_acceptance_rate: "rate",
  order_completion_rate: "rate",
  avg_duration_min: "duration",
  avg_accept_time_min: "duration",
  avg_distance_km: "distance",
};

const metricGroupLabels: Record<MetricKind, string> = {
  count: "Количественные показатели",
  currency: "Денежные показатели",
  rate: "Доли и конверсии",
  duration: "Длительность",
  distance: "Дистанция",
  other: "Прочие показатели",
};

export function getRoleLabel(role: string) {
  return roleLabels[role] ?? role;
}

export function getStatusLabel(status: string) {
  return statusLabels[status] ?? status;
}

export function getChartTypeLabel(chartType?: string | null) {
  if (!chartType) return "Не задан";
  return chartTypeLabels[chartType] ?? chartType;
}

export function getAuditEventLabel(eventType: string) {
  return auditEventLabels[eventType] ?? eventType;
}

export function getChannelLabel(channel: string) {
  return channelLabels[channel] ?? channel;
}

export function formatAnalyticsValue(value: unknown) {
  if (typeof value !== "string") {
    return value;
  }
  return analyticsValueLabels[value] ?? value;
}

export function getMetricKind(metricKey: string): MetricKind {
  return metricKindByKey[metricKey] ?? "other";
}

export function getMetricGroupLabel(metricKind: MetricKind) {
  return metricGroupLabels[metricKind] ?? metricGroupLabels.other;
}

export function buildColumnLabels(plan?: QueryPlan | null) {
  const labels: Record<string, string> = {
    period_label: "Период",
  };

  if (!plan) {
    return labels;
  }

  plan.dimensions.forEach((item) => {
    labels[item.key] = item.label;
  });
  plan.metrics.forEach((item) => {
    labels[item.key] = item.label;
  });

  return labels;
}
