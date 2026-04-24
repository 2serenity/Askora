"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pin, PinOff, RefreshCw, Save, Send, ShieldCheck, Sparkles, Trash2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { ReportSaveDialog } from "@/components/reports/report-save-dialog";
import { ReportShareDialog } from "@/components/reports/report-share-dialog";
import { ScheduleDialog } from "@/components/reports/schedule-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ChartPanel } from "@/components/workspace/chart-panel";
import { ResultTable } from "@/components/workspace/result-table";
import { UnderstandingPanel } from "@/components/workspace/understanding-panel";
import { useQueryRunner } from "@/hooks/use-query-runner";
import { api } from "@/lib/api";
import { getChartTypeLabel, getStatusLabel } from "@/lib/presentation";
import { downloadCsv } from "@/lib/utils";
import type { QueryResult } from "@/types/api";

const fallbackExamples = [
  "Покажи выполненные заказы, отмены и выручку по дням за прошлую неделю",
  "На сколько процентов поднялся или опустился доход в марте относительно февраля",
  "Сравни выручку за 6 марта и 8 марта и 9 марта не линейными графиками",
  "Покажи среднюю цену заказа по часам за вчера",
];

const builderFragments = [
  "выполненные заказы",
  "отмены",
  "выручку",
  "среднюю цену заказа",
  "по дням",
  "по городам",
  "по часам",
  "за вчера",
  "за прошлую неделю",
  "за прошлый месяц",
];

const composingHints = [
  "Что посчитать: выполненные заказы, отмены, выручку, среднюю цену.",
  "Как разбить: по дням, по городам, по часам, по статусам.",
  "За какой период: за вчера, за прошлую неделю, с даты по дату, март относительно февраля.",
];

export function QueryWorkspace() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const autoRunSignatureRef = useRef<string | null>(null);
  const [question, setQuestion] = useState(fallbackExamples[0]);
  const [savedReportId, setSavedReportId] = useState<string | null>(null);
  const [chartTypeOverride, setChartTypeOverride] = useState<QueryResult["visualization"]["chart_type"] | null>(null);

  const mutation = useQueryRunner();
  const history = useQuery({ queryKey: ["query-history"], queryFn: api.queryHistory });
  const examples = useQuery({ queryKey: ["query-examples"], queryFn: api.queryExamples });
  const templates = useQuery({ queryKey: ["query-templates"], queryFn: api.queryTemplates });

  const saveExample = useMutation({
    mutationFn: (payload: { text: string; is_pinned?: boolean }) => api.createQueryExample(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["query-examples"] });
    },
  });

  const removeExample = useMutation({
    mutationFn: (id: string) => api.deleteQueryExample(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["query-examples"] });
    },
  });

  useEffect(() => {
    const presetQuestion = searchParams.get("question");
    if (presetQuestion) {
      setQuestion(presetQuestion);
    }
  }, [searchParams]);

  useEffect(() => {
    const presetQuestion = searchParams.get("question")?.replace(/\s+/g, " ").trim();
    const autoRunSource = searchParams.get("autorun");
    if (!presetQuestion || !autoRunSource) {
      return;
    }

    const signature = `${autoRunSource}:${presetQuestion}`;
    if (autoRunSignatureRef.current === signature) {
      return;
    }

    autoRunSignatureRef.current = signature;
    mutation.mutate({ question: presetQuestion, dry_run: false });
  }, [mutation, searchParams]);

  const normalizedQuestion = useMemo(() => question.replace(/\s+/g, " ").trim(), [question]);

  const mergedExamples = useMemo(() => {
    const custom = [...(examples.data ?? [])].sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned));
    const fallback = fallbackExamples
      .filter((item) => !custom.some((example) => example.text.toLowerCase() === item.toLowerCase()))
      .map((text) => ({ id: `fallback-${text}`, text, is_pinned: false }));
    return [...custom, ...fallback];
  }, [examples.data]);

  const templateExamples = useMemo(() => {
    return (templates.data ?? []).map((item) => ({
      title: item.name,
      text: item.example_question,
      hint: item.description,
    }));
  }, [templates.data]);

  const result = mutation.data;
  const displayResult = useMemo(() => {
    if (!result) {
      return null;
    }
    if (!chartTypeOverride) {
      return result;
    }
    return {
      ...result,
      visualization: {
        ...result.visualization,
        chart_type: chartTypeOverride,
      },
    };
  }, [chartTypeOverride, result]);

  useEffect(() => {
    setSavedReportId(null);
    setChartTypeOverride(null);
  }, [result?.question, result?.generated_sql]);

  function applyFragment(fragment: string) {
    setQuestion((current) => {
      const normalizedCurrent = current.trim();
      if (!normalizedCurrent) {
        return fragment;
      }
      if (normalizedCurrent.toLowerCase().includes(fragment.toLowerCase())) {
        return normalizedCurrent;
      }
      return `${normalizedCurrent} ${fragment}`.trim();
    });
  }

  function runQuery(dryRun = false) {
    if (!normalizedQuestion) {
      return;
    }
    mutation.mutate({ question: normalizedQuestion, dry_run: dryRun });
  }

  function runSpecificQuestion(nextQuestion: string, dryRun = false) {
    const normalized = nextQuestion.replace(/\s+/g, " ").trim();
    if (!normalized) {
      return;
    }
    setQuestion(normalized);
    mutation.mutate({ question: normalized, dry_run: dryRun });
  }

  function addCurrentExample() {
    if (!normalizedQuestion) {
      return;
    }
    saveExample.mutate({ text: normalizedQuestion });
  }

  const statusCard = displayResult ? (
    <Card className="animate-soft-in">
      <CardHeader>
        <CardTitle>Статус и действия</CardTitle>
        <CardDescription>{displayResult.user_message}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant={displayResult.status === "executed" ? "success" : displayResult.status === "blocked" ? "danger" : "warning"}>
            {getStatusLabel(displayResult.status)}
          </Badge>
          <Badge variant="outline">{displayResult.row_count} строк</Badge>
          <Badge variant="outline">{getChartTypeLabel(displayResult.visualization.chart_type)}</Badge>
        </div>

        {!!displayResult.suggestions.length && (
          <div className="rounded-2xl border border-border/80 bg-black/26 p-4 text-sm text-muted-foreground">
            {displayResult.suggestions.map((item) => (
              <div key={item}>{item}</div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          {displayResult.status === "executed" ? <ReportSaveDialog result={displayResult} onSaved={setSavedReportId} /> : null}
          {savedReportId ? <ScheduleDialog reportId={savedReportId} /> : null}
          {savedReportId ? <ReportShareDialog reportId={savedReportId} reportName={displayResult.question} /> : null}
          {displayResult.status === "executed" ? (
            <Button variant="outline" onClick={() => downloadCsv("query-result.csv", displayResult.rows)}>
              <Save className="mr-2 h-4 w-4" />
              Скачать CSV
            </Button>
          ) : null}
        </div>
        {savedReportId ? (
          <div className="rounded-2xl border border-primary/18 bg-primary/8 p-3 text-sm text-primary">
            Отчёт сохранён. Следующие шаги для демо: настройте расписание и сразу поделитесь отчётом с рабочей группой.
          </div>
        ) : null}
      </CardContent>
    </Card>
  ) : null;

  return (
    <div className="space-y-4">
      {statusCard}

      {displayResult ? (
        <div className="animate-soft-in">
          <ChartPanel result={displayResult} onChartTypeChange={setChartTypeOverride} />
        </div>
      ) : null}

      {displayResult ? (
        <div className="animate-soft-in space-y-4">
          <UnderstandingPanel
            plan={displayResult.query_plan}
            sql={displayResult.generated_sql}
            validation={displayResult.validation}
            processingTrace={displayResult.processing_trace}
          />
        </div>
      ) : null}

      {displayResult ? (
        <>
          {displayResult.comparison_summary?.items?.length ? (
            <Card className="animate-soft-in">
              <CardHeader>
                <CardTitle>Сравнительный анализ</CardTitle>
                <CardDescription>Автоматически рассчитанная дельта между текущим и предыдущим периодом.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {displayResult.comparison_summary.items.map((item) => (
                  <div key={item.label} className="rounded-2xl border border-border/80 bg-black/24 p-4">
                    <div className="text-sm text-muted-foreground">{item.label}</div>
                    <div className="mt-2 text-lg font-semibold">
                      {item.current} vs {item.previous}
                    </div>
                    <div className={`mt-2 text-sm ${item.delta >= 0 ? "text-primary" : "text-rose-300"}`}>
                      Δ {item.delta} {item.delta_pct !== null && item.delta_pct !== undefined ? `(${item.delta_pct}%)` : ""}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}

          <ResultTable columns={displayResult.columns} rows={displayResult.rows} plan={displayResult.query_plan} />
        </>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_360px]">
        <Card className="overflow-hidden">
          <CardHeader className="border-b border-border/80 bg-black/18">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default">Семантический слой</Badge>
              <Badge variant="outline">Безопасный SQL</Badge>
              <Badge variant="outline">train.csv</Badge>
            </div>
            <CardTitle className="mt-3 text-2xl">Сформулируйте запрос</CardTitle>
            <CardDescription>
              Пишите обычным русским языком. Система должна подстраиваться под пользователя и разбирать составные запросы без SQL.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 pt-4">
            <Textarea
              className="min-h-[120px] text-[15px]"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Например: Покажи выполненные заказы, отмены и выручку по дням за прошлую неделю"
            />

            <div className="space-y-2">
              <Button className="w-full" size="lg" onClick={() => runQuery(false)} disabled={mutation.isPending || !normalizedQuestion}>
                <Send className="mr-2 h-4 w-4" />
                {mutation.isPending ? "Выполняем..." : "Выполнить"}
              </Button>
              <div className="flex flex-wrap gap-3">
                <Button variant="outline" size="lg" onClick={() => runQuery(true)} disabled={mutation.isPending || !normalizedQuestion}>
                  <ShieldCheck className="mr-2 h-4 w-4" />
                  Проверить без запуска
                </Button>
                {displayResult ? (
                  <Button variant="ghost" size="lg" onClick={() => mutation.mutate({ question: displayResult.question })}>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Повторить
                  </Button>
                ) : null}
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Быстрая сборка запроса</div>
              <div className="flex flex-wrap gap-2">
                {builderFragments.map((item) => (
                  <button
                    key={item}
                    className="rounded-full border border-border bg-black/24 px-3 py-1.5 text-sm text-muted-foreground transition hover:border-primary/30 hover:bg-primary/8 hover:text-foreground"
                    onClick={() => applyFragment(item)}
                  >
                    + {item}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Примеры пользователя</div>
                <Button variant="outline" size="sm" onClick={addCurrentExample} disabled={!normalizedQuestion}>
                  Сохранить текущий вопрос
                </Button>
              </div>
              <div className="flex flex-wrap gap-2">
                {mergedExamples.map((item) => {
                  const editable = !item.id.startsWith("fallback-");
                  return (
                    <div key={item.id} className="inline-flex items-center gap-1 rounded-full border border-border bg-black/30 px-2 py-1">
                      <button
                        className="px-1.5 py-1 text-left text-sm text-muted-foreground transition hover:text-foreground"
                        onClick={() => setQuestion(item.text)}
                      >
                        {item.text}
                      </button>
                      {editable ? (
                        <>
                          <button
                            className="rounded-full p-1 text-muted-foreground transition hover:bg-primary/10 hover:text-foreground"
                            onClick={() =>
                              saveExample.mutate({
                                text: item.text,
                                is_pinned: !item.is_pinned,
                              })
                            }
                            title={item.is_pinned ? "Открепить" : "Закрепить"}
                          >
                            {item.is_pinned ? <PinOff className="h-3.5 w-3.5" /> : <Pin className="h-3.5 w-3.5" />}
                          </button>
                          <button
                            className="rounded-full p-1 text-muted-foreground transition hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => removeExample.mutate(item.id)}
                            title="Удалить пример"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Типовые шаблоны вопросов</div>
              <div className="grid gap-2 md:grid-cols-2">
                {templateExamples.map((item) => (
                  <button
                    key={`${item.title}-${item.text}`}
                    className="rounded-2xl border border-border/80 bg-black/24 p-3 text-left transition hover:border-primary/30 hover:bg-primary/8"
                    onClick={() => setQuestion(item.text)}
                  >
                    <div className="text-sm font-medium">{item.title}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{item.hint}</div>
                    <div className="mt-2 text-xs text-primary">{item.text}</div>
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {!displayResult ? (
            <Card className="animate-soft-in">
              <CardHeader>
                <CardTitle>Как лучше задавать вопрос</CardTitle>
                <CardDescription>
                  Система лучше всего работает с конкретной метрикой, разрезом и периодом, но теперь должна понимать и нестандартные формулировки.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-3">
                  {composingHints.map((item) => (
                    <div key={item} className="rounded-2xl border border-border/80 bg-black/24 p-4 text-sm text-muted-foreground">
                      {item}
                    </div>
                  ))}
                  <div className="inline-flex items-center gap-2 rounded-full border border-primary/18 bg-primary/8 px-3 py-2 text-sm text-primary">
                    <Sparkles className="h-4 w-4" />
                    Пишите естественным русским языком, SQL знать не нужно.
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card className="animate-soft-in">
            <CardHeader>
              <CardTitle>Последние запросы</CardTitle>
              <CardDescription>Нажмите на запрос, чтобы сразу выполнить его повторно.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(history.data ?? []).slice(0, 6).map((item) => (
                <button
                  key={item.id}
                  onClick={() => runSpecificQuestion(item.question)}
                  className="w-full rounded-2xl border border-border/80 bg-black/28 p-3.5 text-left transition hover:border-primary/30 hover:bg-primary/8"
                >
                  <div className="text-sm font-medium">{item.question}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {new Date(item.created_at).toLocaleString("ru-RU")} • {getStatusLabel(item.status)}
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>

    </div>
  );
}
