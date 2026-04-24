"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SqlPanel } from "@/components/workspace/sql-panel";
import type { QueryPlan, ValidationResult } from "@/types/api";

export function UnderstandingPanel({
  plan,
  sql,
  validation,
  processingTrace,
}: {
  plan: QueryPlan;
  sql?: string;
  validation?: ValidationResult;
  processingTrace?: Record<string, unknown> | null;
}) {
  const [showSql, setShowSql] = useState(false);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Как система поняла запрос</CardTitle>
        <CardDescription>Интерпретация из семантического слоя и гибридного механизма разбора запроса.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-2 rounded-2xl border border-border/80 bg-black/22 p-4">
            <div className="text-sm font-medium">Метрики</div>
            <div className="flex flex-wrap gap-2">
              {plan.metrics.map((item) => (
                <Badge key={item.key}>{item.label}</Badge>
              ))}
            </div>
          </div>

          <div className="space-y-2 rounded-2xl border border-border/80 bg-black/22 p-4">
            <div className="text-sm font-medium">Измерения</div>
            <div className="flex flex-wrap gap-2">
              {plan.dimensions.length ? (
                plan.dimensions.map((item) => (
                  <Badge key={item.key} variant="outline">
                    {item.label}
                  </Badge>
                ))
              ) : (
                <div className="text-sm text-muted-foreground">Без дополнительной разбивки</div>
              )}
            </div>
          </div>

          <div className="space-y-2 rounded-2xl border border-border/80 bg-black/22 p-4">
            <div className="text-sm font-medium">Фильтры и период</div>
            <div className="text-sm text-muted-foreground">
              {plan.filters.length ? plan.filters.map((item) => `${item.label}: ${String(item.value)}`).join(", ") : "Явных фильтров нет"}
            </div>
            <div className="text-sm text-muted-foreground">
              {plan.time_range.label}: {plan.time_range.start_date} → {plan.time_range.end_date}
            </div>
          </div>

          <div className="space-y-2 rounded-2xl border border-border/80 bg-black/22 p-4">
            <div className="text-sm font-medium">Уверенность интерпретации</div>
            <Badge variant={plan.confidence >= 0.75 ? "success" : plan.confidence >= 0.6 ? "warning" : "danger"}>
              {Math.round(plan.confidence * 100)}%
            </Badge>
            {plan.needs_clarification ? (
              <div className="text-sm text-amber-300">Требуется уточнение: {plan.clarification_questions.join(" ")}</div>
            ) : null}
          </div>
        </div>

        {processingTrace ? (
          <div className="rounded-2xl border border-border/80 bg-black/22 p-4 text-sm text-muted-foreground">
            <div className="mb-2 text-sm font-medium text-foreground">Explain trace</div>
            <div>Источник интерпретации: {String((processingTrace.extraction as { effective_source?: string } | undefined)?.effective_source ?? "unknown")}</div>
            <div>Intent review: {String((processingTrace.intent_review as { adjusted?: boolean } | undefined)?.adjusted ? "корректировка применена" : "без корректировок")}</div>
            <div>SQL review: {String((processingTrace.sql_review as { allowed?: boolean } | undefined)?.allowed ?? "n/a")}</div>
          </div>
        ) : null}

        {sql && validation ? (
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-border/80 bg-black/22 p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Guardrails</div>
                <div className="mt-1 text-sm">{validation.allowed ? "Разрешено к запуску" : "Заблокировано"}</div>
              </div>
              <div className="rounded-2xl border border-border/80 bg-black/22 p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Оценка стоимости</div>
                <div className="mt-1 text-sm">{validation.estimated_cost !== null && validation.estimated_cost !== undefined ? validation.estimated_cost : "n/a"}</div>
              </div>
              <div className="rounded-2xl border border-border/80 bg-black/22 p-3">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Оценка строк</div>
                <div className="mt-1 text-sm">{validation.estimated_rows !== null && validation.estimated_rows !== undefined ? validation.estimated_rows : "n/a"}</div>
              </div>
            </div>
            {validation.blocked_reasons.length ? (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-100">
                {validation.blocked_reasons.map((reason) => (
                  <div key={reason}>- {reason}</div>
                ))}
              </div>
            ) : null}
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => setShowSql((current) => !current)}>
                {showSql ? <ChevronUp className="mr-2 h-4 w-4" /> : <ChevronDown className="mr-2 h-4 w-4" />}
                sql
              </Button>
            </div>
            {showSql ? (
              <div className="sql-reveal">
                <SqlPanel sql={sql} validation={validation} embedded />
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
