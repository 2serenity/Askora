"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, CalendarClock, ExternalLink, Play, Share2, Trash2, Users } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { useRouter } from "next/navigation";

import { ReportPreviewCard } from "@/components/reports/report-preview-card";
import { ReportShareDialog } from "@/components/reports/report-share-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";
import { getChannelLabel, getChartTypeLabel, getStatusLabel } from "@/lib/presentation";
import { formatNumber } from "@/lib/utils";

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

function formatDateTime(value?: string | null) {
  if (!value) {
    return "Пока нет данных";
  }
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getRunSourceLabel(source: string) {
  const labels: Record<string, string> = {
    initial_save: "Сохранение отчёта",
    manual_rerun: "Повторный запуск",
    schedule: "Запуск по расписанию",
  };
  return labels[source] ?? source;
}

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const auth = useAuth();

  const report = useQuery({
    queryKey: ["report", params.id],
    queryFn: () => api.report(params.id),
  });

  const canManage =
    auth.data?.user.role === "admin" || (auth.data?.user.id && auth.data.user.id === report.data?.owner_id);

  const rerun = useMutation({
    mutationFn: () => api.rerunReport(params.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report", params.id] });
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["reports", "shared"] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      await queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
  });

  const deleteReport = useMutation({
    mutationFn: () => api.deleteReport(params.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["reports", "shared"] });
      await queryClient.invalidateQueries({ queryKey: ["schedules"] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      router.push("/reports");
    },
  });

  const deleteSchedule = useMutation({
    mutationFn: (scheduleId: string) => api.deleteSchedule(scheduleId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report", params.id] });
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["schedules"] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const sortedRuns = useMemo(
    () =>
      [...(report.data?.runs ?? [])].sort(
        (left, right) => new Date(right.executed_at).getTime() - new Date(left.executed_at).getTime(),
      ),
    [report.data?.runs],
  );

  const latestRun = sortedRuns[0] ?? null;
  const metricLabels = useMemo(
    () => extractMetricLabels(report.data?.query_plan_json ?? {}),
    [report.data?.query_plan_json],
  );
  const periodLabel = useMemo(
    () => extractPeriodLabel(report.data?.query_plan_json ?? {}),
    [report.data?.query_plan_json],
  );
  const previewPayload = latestRun?.result_preview_json ?? report.data?.result_preview_json ?? {};

  if (report.isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">Загружаем отчёт...</CardContent>
      </Card>
    );
  }

  if (!report.data) {
    return (
      <Card>
        <CardContent className="pt-6">Отчёт не найден.</CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">Сохранённый отчёт</Badge>
            <Badge variant="outline">{getChartTypeLabel(report.data.chart_type)}</Badge>
            {report.data.last_run_status ? <Badge variant="outline">{getStatusLabel(report.data.last_run_status)}</Badge> : null}
            {periodLabel ? <Badge variant="outline">{periodLabel}</Badge> : null}
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">{report.data.name}</h1>
          <p className="max-w-4xl text-sm text-muted-foreground">
            {report.data.description || report.data.question}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button asChild>
            <Link href={`/workspace?question=${encodeURIComponent(report.data.question)}`}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Открыть в workspace
            </Link>
          </Button>
          <Button variant="outline" onClick={() => rerun.mutate()} disabled={rerun.isPending}>
            <Play className="mr-2 h-4 w-4" />
            {rerun.isPending ? "Запускаем..." : "Запустить заново"}
          </Button>
          {canManage ? <ReportShareDialog reportId={report.data.id} reportName={report.data.name} /> : null}
          {canManage ? (
            <Button
              variant="danger"
              onClick={() => {
                if (window.confirm("Удалить этот отчёт?")) {
                  deleteReport.mutate();
                }
              }}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Удалить
            </Button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-primary/14 bg-black/28">
          <CardContent className="pt-5">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Метрики</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{metricLabels.length || "—"}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              {metricLabels.length ? metricLabels.slice(0, 3).join(", ") : "Состав метрик определён в плане отчёта"}
            </div>
          </CardContent>
        </Card>
        <Card className="border-primary/14 bg-black/28">
          <CardContent className="pt-5">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Последний запуск</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">
              {report.data.last_run_row_count !== null && report.data.last_run_row_count !== undefined
                ? formatNumber(report.data.last_run_row_count)
                : "—"}
            </div>
            <div className="mt-1 text-sm text-muted-foreground">{formatDateTime(report.data.last_run_at)}</div>
          </CardContent>
        </Card>
        <Card className="border-primary/14 bg-black/28">
          <CardContent className="pt-5">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Расписания</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{report.data.schedules.length}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              {report.data.schedules.length ? "Автоматические отправки включены" : "Пока без автозапуска"}
            </div>
          </CardContent>
        </Card>
        <Card className="border-primary/14 bg-black/28">
          <CardContent className="pt-5">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Поделились</div>
            <div className="mt-2 text-2xl font-semibold text-foreground">{report.data.shares.length}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              {report.data.shares.length ? "Отчёт уже открыт коллегам" : "Отчёт пока личный"}
            </div>
          </CardContent>
        </Card>
      </div>

      <ReportPreviewCard
        title={report.data.name}
        subtitle="Актуальный вид отчёта"
        question={report.data.question}
        chartType={report.data.chart_type}
        metricLabels={metricLabels}
        periodLabel={periodLabel}
        preview={previewPayload}
        queryPlan={report.data.query_plan_json}
        note={
          latestRun
            ? `Последний запуск выполнен ${formatDateTime(latestRun.executed_at)}. В карточке показано живое превью с графиком и ключевыми строками результата.`
            : "Как только отчёт будет выполнен, здесь появятся график, показатели и краткая таблица."
        }
        actions={
          <>
            <Badge variant="outline">
              <Activity className="mr-1.5 h-3.5 w-3.5" />
              {sortedRuns.length} запусков
            </Badge>
            <Badge variant="outline">
              <CalendarClock className="mr-1.5 h-3.5 w-3.5" />
              {report.data.schedules.length} расписаний
            </Badge>
            <Badge variant="outline">
              <Share2 className="mr-1.5 h-3.5 w-3.5" />
              {report.data.shares.length} публикаций
            </Badge>
          </>
        }
      />

      <Tabs defaultValue="runs" className="space-y-4">
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="runs">Запуски</TabsTrigger>
          <TabsTrigger value="schedules">Расписание</TabsTrigger>
          <TabsTrigger value="shares">Доступ</TabsTrigger>
          <TabsTrigger value="technical">Технически</TabsTrigger>
        </TabsList>

        <TabsContent value="runs" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle>История запусков</CardTitle>
              <CardDescription>Показываем только результат выполнения и статус, без лишней технической перегрузки.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {sortedRuns.length ? (
                sortedRuns.map((run, index) => (
                  <div key={run.id} className="rounded-[24px] border border-border/80 bg-black/22 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={index === 0 ? "success" : "secondary"}>
                            {index === 0 ? "Последний" : `Запуск ${sortedRuns.length - index}`}
                          </Badge>
                          <Badge variant="outline">{getStatusLabel(run.status)}</Badge>
                          <Badge variant="outline">{getRunSourceLabel(run.trigger_source)}</Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {formatDateTime(run.executed_at)} • {formatNumber(run.row_count)} строк
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-black/18 p-5 text-sm text-muted-foreground">
                  Запусков пока нет. Выполните отчёт заново, чтобы сохранить свежий результат.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="schedules" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle>Расписания отправки</CardTitle>
              <CardDescription>Отчёт можно запускать автоматически и отправлять коллегам или в рабочую группу.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {report.data.schedules.length ? (
                report.data.schedules.map((schedule) => (
                  <div key={schedule.id} className="rounded-[24px] border border-border/80 bg-black/22 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={schedule.is_active ? "success" : "secondary"}>
                            {schedule.is_active ? "Активно" : "Пауза"}
                          </Badge>
                          <Badge variant="outline">{getChannelLabel(schedule.channel)}</Badge>
                        </div>
                        <div className="text-sm text-foreground">{schedule.cron_expression}</div>
                        <div className="text-sm text-muted-foreground">
                          {schedule.channel === "group" ? "Отправка в рабочую группу" : schedule.recipient || "Внутренний канал"} •{" "}
                          {schedule.timezone}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Последний запуск: {formatDateTime(schedule.last_run_at)} • Следующий запуск: {formatDateTime(schedule.next_run_at)}
                        </div>
                      </div>

                      {canManage ? (
                        <Button
                          variant="outline"
                          onClick={() => {
                            if (window.confirm("Удалить это расписание?")) {
                              deleteSchedule.mutate(schedule.id);
                            }
                          }}
                        >
                          Удалить расписание
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-black/18 p-5 text-sm text-muted-foreground">
                  Пока нет расписаний. Отчёт можно запускать вручную или настроить автозапуск из каталога отчётов.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="shares" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle>Где отчёт доступен коллегам</CardTitle>
              <CardDescription>Показываем рабочие группы, в которые уже опубликован этот отчёт.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {report.data.shares.length ? (
                report.data.shares.map((share) => (
                  <div key={share.id} className="rounded-[24px] border border-border/80 bg-black/22 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">
                            <Users className="mr-1.5 h-3.5 w-3.5" />
                            {share.group_name}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Поделился: {share.shared_by_name} • {formatDateTime(share.created_at)}
                        </div>
                        {share.note ? <div className="text-sm text-foreground">{share.note}</div> : null}
                      </div>
                      <Button asChild variant="outline">
                        <Link href="/groups">Открыть группу</Link>
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-[24px] border border-dashed border-border/80 bg-black/18 p-5 text-sm text-muted-foreground">
                  Этот отчёт пока не опубликован в рабочие группы.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="technical" className="mt-0">
          <Card>
            <CardHeader>
              <CardTitle>Техническая часть</CardTitle>
              <CardDescription>
                Этот раздел нужен для проверки и сопровождения. Основной пользовательский экран отчёта расположен выше.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-[24px] border border-border/80 bg-black/22 p-4">
                <div className="mb-3 text-sm font-medium text-foreground">SQL запроса</div>
                <pre className="overflow-x-auto rounded-2xl bg-slate-950 p-4 text-sm text-slate-50">{report.data.sql_text}</pre>
              </div>
              <div className="rounded-[24px] border border-border/80 bg-black/22 p-4">
                <div className="mb-3 text-sm font-medium text-foreground">План запроса</div>
                <pre className="overflow-x-auto rounded-2xl border border-border/80 bg-black/20 p-4 text-sm text-muted-foreground">
                  {JSON.stringify(report.data.query_plan_json, null, 2)}
                </pre>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
