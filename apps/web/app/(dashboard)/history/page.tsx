"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LineChart } from "lucide-react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { getChartTypeLabel, getStatusLabel } from "@/lib/presentation";

export default function HistoryPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { data, isLoading } = useQuery({
    queryKey: ["query-history"],
    queryFn: api.queryHistory
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteHistoryItem(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["query-history"] });
    },
  });
  const clearMutation = useMutation({
    mutationFn: api.clearHistory,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["query-history"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">История запросов</h1>
          <p className="mt-2 text-muted-foreground">Полный журнал выполнений, блокировок и запросов на уточнение.</p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            if (window.confirm("Очистить всю историю запросов?")) {
              clearMutation.mutate();
            }
          }}
          disabled={!data?.length || clearMutation.isPending}
        >
          {clearMutation.isPending ? "Очищаем…" : "Очистить историю"}
        </Button>
      </div>

      <div className="grid gap-4">
        {isLoading && <Card><CardContent className="pt-6">Загружаем историю…</CardContent></Card>}
        {data?.map((item) => (
          <Card key={item.id}>
            <CardHeader className="gap-3 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1">
                <CardTitle className="text-xl">{item.question}</CardTitle>
                <CardDescription>
                  {new Date(item.created_at).toLocaleString("ru-RU")} • строк: {item.row_count}
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant={item.status === "executed" ? "success" : item.status === "blocked" ? "danger" : "warning"}>
                  {getStatusLabel(item.status)}
                </Badge>
                <Badge variant="outline">Уверенность {Math.round(item.confidence * 100)}%</Badge>
                {item.chart_type ? <Badge variant="outline">{getChartTypeLabel(item.chart_type)}</Badge> : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-xl border border-border/80 bg-black/24 p-4 text-sm text-muted-foreground">
                <div className="mb-2 text-xs uppercase tracking-[0.2em]">SQL</div>
                <pre className="overflow-x-auto whitespace-pre-wrap">{item.sql_text || "SQL не был выполнен"}</pre>
              </div>
              <div className="flex justify-end gap-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    const params = new URLSearchParams({
                      question: item.question,
                      autorun: `history-${item.id}`,
                    });
                    router.push(`/workspace?${params.toString()}`);
                  }}
                >
                  <LineChart className="mr-2 h-4 w-4" />
                  Открыть график
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    if (window.confirm("Удалить эту запись из истории?")) {
                      deleteMutation.mutate(item.id);
                    }
                  }}
                >
                  Удалить запись
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
