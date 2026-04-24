"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { ReportCatalog } from "@/components/reports/report-catalog";
import { ReportPreviewCard } from "@/components/reports/report-preview-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { getStatusLabel } from "@/lib/presentation";

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

export default function ReportsPage() {
  const reports = useQuery({ queryKey: ["reports"], queryFn: api.reports });
  const sharedReports = useQuery({ queryKey: ["reports", "shared"], queryFn: api.sharedReports });
  const schedules = useQuery({ queryKey: ["schedules"], queryFn: api.schedules });

  const ownReportsCount = reports.data?.length ?? 0;
  const activeSchedulesCount = schedules.data?.filter((item) => item.is_active).length ?? 0;
  const sharedReportsCount = sharedReports.data?.length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Сохранённые отчёты</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Здесь собраны ваши отчёты, последние запуски, расписания и материалы, которыми с вами поделились коллеги.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Моих отчётов</CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{ownReportsCount}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Активных расписаний</CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{activeSchedulesCount}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Поделились со мной</CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{sharedReportsCount}</CardContent>
        </Card>
      </div>

      <ReportCatalog reports={reports.data ?? []} schedules={schedules.data ?? []} isLoading={reports.isLoading} />

      <Card>
        <CardHeader>
          <CardTitle>Отчёты из рабочих групп</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {(sharedReports.data ?? []).length ? (
            sharedReports.data?.map((item) => (
              <div key={item.id} className="space-y-3 rounded-[28px] border border-border/80 bg-black/20 p-4">
                <ReportPreviewCard
                  compact
                  title={item.name}
                  question={item.description || item.question}
                  chartType={item.chart_type}
                  metricLabels={extractMetricLabels(item.query_plan_json)}
                  periodLabel={extractPeriodLabel(item.query_plan_json)}
                  preview={item.result_preview_json}
                  queryPlan={item.query_plan_json}
                  subtitle={item.last_run_status ? `Последний запуск: ${getStatusLabel(item.last_run_status)}` : "Общий отчёт"}
                  actions={
                    <>
                      <Badge variant="outline">{item.runs_count} запусков</Badge>
                      <Badge variant="outline">{item.shares_count} публикаций</Badge>
                    </>
                  }
                />
                <div className="flex flex-wrap gap-3">
                  <Button variant="outline" asChild>
                    <Link href={`/reports/${item.id}`}>Открыть отчёт</Link>
                  </Button>
                  <Button variant="ghost" asChild>
                    <Link href="/groups">Открыть группу</Link>
                  </Button>
                </div>
              </div>
            ))
          ) : (
            <div className="text-sm text-muted-foreground">В рабочих группах вам пока не открывали отчёты.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
