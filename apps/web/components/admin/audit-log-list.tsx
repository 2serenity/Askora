"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyablePre } from "@/components/ui/copyable-pre";
import { api } from "@/lib/api";
import { getAuditEventLabel, getStatusLabel } from "@/lib/presentation";

export function AuditLogList() {
  const { data } = useQuery({
    queryKey: ["admin", "audit-logs"],
    queryFn: api.auditLogs,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Журнал аудита</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {(data ?? []).map((entry) => (
          <div key={entry.id} className="rounded-2xl border border-border/80 bg-black/24 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={entry.status === "success" || entry.status === "executed" ? "success" : entry.status === "blocked" ? "danger" : "warning"}>
                {getAuditEventLabel(entry.event_type)}
              </Badge>
              <Badge variant="outline">{getStatusLabel(entry.status)}</Badge>
              {entry.row_count ? <Badge variant="outline">{entry.row_count} строк</Badge> : null}
            </div>
            <div className="mt-2 text-sm">{entry.question || "Системное событие"}</div>
            {entry.blocked_reason ? <div className="mt-2 text-sm text-rose-300">{entry.blocked_reason}</div> : null}
            {entry.sql_text ? (
              <details className="mt-3 rounded-xl border border-border/70 bg-black/18 p-3">
                <summary className="cursor-pointer text-sm font-medium">Показать SQL</summary>
                <CopyablePre value={entry.sql_text} className="mt-3" preClassName="overflow-x-auto rounded-xl bg-slate-950 p-3 text-xs text-slate-50" />
              </details>
            ) : null}
            <div className="mt-2 text-xs text-muted-foreground">{new Date(entry.created_at).toLocaleString("ru-RU")}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
