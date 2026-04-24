"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { ReportPreviewCard } from "@/components/reports/report-preview-card";
import { ReportShareDialog } from "@/components/reports/report-share-dialog";
import { ScheduleDialog } from "@/components/reports/schedule-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { getStatusLabel } from "@/lib/presentation";
import type { ReportSummary, ScheduleSummary } from "@/types/api";

function extractMetricLabels(queryPlan: Record<string, unknown>) {
  const metrics = queryPlan.metrics;
  if (!Array.isArray(metrics)) {
    return [] as string[];
  }
  return metrics
    .map((item) => (item && typeof item === "object" && "label" in item ? String(item.label) : ""))
    .filter(Boolean);
}

function extractPeriodLabel(queryPlan: Record<string, unknown>) {
  const timeRange = queryPlan.time_range;
  if (!timeRange || typeof timeRange !== "object" || !("label" in timeRange)) {
    return undefined;
  }
  return String(timeRange.label);
}

export function ReportCatalog({
  reports,
  schedules,
  isLoading,
}: {
  reports: ReportSummary[];
  schedules: ScheduleSummary[];
  isLoading?: boolean;
}) {
  const queryClient = useQueryClient();
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);

  const deleteReport = useMutation({
    mutationFn: (reportId: string) => api.deleteReport(reportId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["reports", "shared"] });
      await queryClient.invalidateQueries({ queryKey: ["schedules"] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      setSelectedReportId(null);
    },
  });

  const deleteSchedule = useMutation({
    mutationFn: (scheduleId: string) => api.deleteSchedule(scheduleId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["schedules"] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  return (
    <div className="grid gap-4">
      {isLoading ? (
        <Card>
          <CardContent className="pt-6">Загружаем отчёты…</CardContent>
        </Card>
      ) : null}

      {!isLoading && !reports.length ? (
        <Card>
          <CardContent className="pt-6 text-muted-foreground">
            Сохранённых отчётов пока нет. Выполните запрос в рабочей области и сохраните его.
          </CardContent>
        </Card>
      ) : null}

      {reports.map((report) => {
        const reportSchedules = schedules.filter((item) => item.report_id === report.id);
        const metricLabels = extractMetricLabels(report.query_plan_json);
        const periodLabel = extractPeriodLabel(report.query_plan_json);

        return (
          <Card key={report.id} className="overflow-hidden">
            <CardContent className="space-y-4 p-4">
              <ReportPreviewCard
                compact
                title={report.name}
                question={report.description || report.question}
                chartType={report.chart_type}
                metricLabels={metricLabels}
                periodLabel={periodLabel}
                preview={report.result_preview_json}
                queryPlan={report.query_plan_json}
                subtitle={report.last_run_status ? `Последний запуск: ${getStatusLabel(report.last_run_status)}` : "Сохранённый отчёт"}
                actions={
                  <>
                    <Badge variant="outline">{report.runs_count} запусков</Badge>
                    <Badge variant={reportSchedules.length ? "success" : "secondary"}>
                      {reportSchedules.length ? `${reportSchedules.length} расписаний` : "Без расписания"}
                    </Badge>
                  </>
                }
              />

              <div className="flex flex-wrap gap-3">
                <Button variant="outline" asChild>
                  <Link href={`/reports/${report.id}`}>Открыть отчёт</Link>
                </Button>
                <ReportShareDialog reportId={report.id} reportName={report.name} />
                <Button variant="secondary" onClick={() => setSelectedReportId((current) => (current === report.id ? null : report.id))}>
                  {selectedReportId === report.id ? "Скрыть расписание" : "Настроить расписание"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (window.confirm("Удалить отчёт и связанные расписания?")) {
                      deleteReport.mutate(report.id);
                    }
                  }}
                >
                  Удалить
                </Button>
              </div>

              {selectedReportId === report.id ? <ScheduleDialog reportId={report.id} /> : null}

              {reportSchedules.length ? (
                <div className="grid gap-2 md:grid-cols-2">
                  {reportSchedules.map((schedule) => (
                    <div key={schedule.id} className="rounded-2xl border border-border/80 bg-black/20 px-4 py-3 text-sm text-muted-foreground">
                      <div className="font-medium text-foreground">{schedule.channel === "group" ? "Отправка в группу" : "Автоотправка"}</div>
                      <div className="mt-1">{schedule.cron_expression}</div>
                      <div className="mt-1">
                        {schedule.channel === "group" ? "Рабочая группа" : schedule.recipient} • {schedule.timezone}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="mt-3"
                        onClick={() => {
                          if (window.confirm("Удалить это расписание?")) {
                            deleteSchedule.mutate(schedule.id);
                          }
                        }}
                      >
                        Удалить расписание
                      </Button>
                    </div>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
