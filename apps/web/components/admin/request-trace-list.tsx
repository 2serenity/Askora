"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyablePre } from "@/components/ui/copyable-pre";
import { api } from "@/lib/api";
import { getAuditEventLabel, getStatusLabel } from "@/lib/presentation";

function formatJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function readTrace(entry: { extra_json?: Record<string, unknown> }) {
  const extra = entry.extra_json ?? {};
  const trace = extra.trace;
  return trace && typeof trace === "object" ? (trace as Record<string, unknown>) : null;
}

export function RequestTraceList() {
  const { data } = useQuery({
    queryKey: ["admin", "audit-logs"],
    queryFn: api.auditLogs,
  });

  const items = (data ?? []).filter((entry) => entry.question);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Как система обрабатывает запрос</CardTitle>
        <CardDescription>
          Здесь видно, участвовала ли LLM, что разобралось правилами, какой SQL был собран и почему запрос был выполнен или заблокирован.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {items.map((entry) => {
          const trace = readTrace(entry);
          const extraction = trace?.extraction as Record<string, unknown> | undefined;
          const llm = extraction?.llm as Record<string, unknown> | undefined;
          const resolvedPlan =
            (trace?.resolved_plan_after_review as Record<string, unknown> | undefined) ??
            (trace?.resolved_plan as Record<string, unknown> | undefined);
          const sqlReview = trace?.sql_review as Record<string, unknown> | undefined;
          const guardrails = trace?.guardrails as Record<string, unknown> | undefined;
          const llmStatus = typeof llm?.status === "string" ? llm.status : "unknown";
          const effectiveSource = typeof extraction?.effective_source === "string" ? extraction.effective_source : "unknown";
          const metrics = Array.isArray(resolvedPlan?.metrics) ? resolvedPlan?.metrics : [];
          const dimensions = Array.isArray(resolvedPlan?.dimensions) ? resolvedPlan?.dimensions : [];

          return (
            <div key={entry.id} className="rounded-2xl border border-border/80 bg-black/24 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={entry.status === "success" || entry.status === "executed" ? "success" : entry.status === "blocked" ? "danger" : "warning"}>
                  {getAuditEventLabel(entry.event_type)}
                </Badge>
                <Badge variant="outline">{getStatusLabel(entry.status)}</Badge>
                <Badge variant={effectiveSource === "hybrid" ? "default" : "outline"}>
                  {effectiveSource === "hybrid" ? "AI + правила" : "Rules only"}
                </Badge>
                <Badge variant="outline">LLM: {llmStatus}</Badge>
              </div>

              <div className="mt-3 text-sm font-medium">{entry.question}</div>
              {entry.blocked_reason ? <div className="mt-2 text-sm text-rose-300">{entry.blocked_reason}</div> : null}

              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-border/70 bg-black/18 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Метрики</div>
                  <div className="mt-2 text-sm text-foreground">{metrics.length ? metrics.join(", ") : "—"}</div>
                </div>
                <div className="rounded-xl border border-border/70 bg-black/18 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Разрезы</div>
                  <div className="mt-2 text-sm text-foreground">{dimensions.length ? dimensions.join(", ") : "—"}</div>
                </div>
                <div className="rounded-xl border border-border/70 bg-black/18 p-3">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Период</div>
                  <div className="mt-2 text-sm text-foreground">
                    {typeof resolvedPlan?.time_range === "object" && resolvedPlan?.time_range
                      ? JSON.stringify(resolvedPlan.time_range)
                      : "—"}
                  </div>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span>SQL review: {sqlReview?.allowed === false ? "blocked" : "ok"}</span>
                <span>•</span>
                <span>Guardrails: {guardrails?.allowed === false ? "blocked" : "ok"}</span>
                <span>•</span>
                <span>{new Date(entry.created_at).toLocaleString("ru-RU")}</span>
              </div>

              <details className="mt-4 rounded-xl border border-border/70 bg-black/16 p-3">
                <summary className="cursor-pointer text-sm font-medium">Подробный trace</summary>
                <div className="mt-3 space-y-3">
                  {entry.sql_text ? (
                    <div>
                      <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">SQL</div>
                      <CopyablePre value={entry.sql_text} preClassName="overflow-x-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-50" />
                    </div>
                  ) : null}
                  <div>
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">LLM / extraction</div>
                    <pre className="overflow-x-auto rounded-xl border border-border/70 bg-black/20 p-3 text-xs text-muted-foreground">
                      {formatJson(extraction)}
                    </pre>
                  </div>
                  <div>
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">Resolved plan</div>
                    <pre className="overflow-x-auto rounded-xl border border-border/70 bg-black/20 p-3 text-xs text-muted-foreground">
                      {formatJson(resolvedPlan)}
                    </pre>
                  </div>
                  <div>
                    <div className="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">Guardrails</div>
                    <pre className="overflow-x-auto rounded-xl border border-border/70 bg-black/20 p-3 text-xs text-muted-foreground">
                      {formatJson(guardrails)}
                    </pre>
                  </div>
                </div>
              </details>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
