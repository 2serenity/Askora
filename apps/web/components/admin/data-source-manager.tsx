"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { CsvAutoResolutionCandidate } from "@/types/api";

const schema = z.object({
  key: z.string().min(2),
  name: z.string().min(2),
  description: z.string().optional(),
  dialect: z.string().min(2),
  connection_url: z.string().min(5),
  schema_name: z.string().optional(),
  allowed_roles: z.string().optional(),
});

const csvSchema = z.object({
  file: z.custom<FileList>((value) => value instanceof FileList && value.length > 0, "Выберите CSV-файл"),
  source_key: z.string().optional(),
  table_name: z.string().optional(),
  delimiter: z.string().min(1).max(8),
  auto_mode: z.boolean().default(true),
  apply: z.boolean().default(false),
});

export function DataSourceManager() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["admin", "data-sources"],
    queryFn: api.dataSources,
  });

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      key: "default",
      name: "Основной PostgreSQL",
      description: "",
      dialect: "postgres",
      connection_url: "postgresql+psycopg://postgres:postgres@db:5432/analytics_hub",
      schema_name: "analytics",
      allowed_roles: "admin, analyst, business_user",
    },
  });

  const csvForm = useForm<z.infer<typeof csvSchema>>({
    resolver: zodResolver(csvSchema),
    defaultValues: {
      file: undefined,
      source_key: "",
      table_name: "",
      delimiter: "auto",
      auto_mode: true,
      apply: true,
    },
  });

  const mutation = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      api.createDataSource({
        key: values.key.trim(),
        name: values.name.trim(),
        description: values.description?.trim() || "",
        dialect: values.dialect.trim(),
        connection_url: values.connection_url.trim(),
        schema_name: values.schema_name?.trim() || "",
        is_active: true,
        is_default: values.key.trim() === "default",
        allowed_roles_json: values.allowed_roles
          ? values.allowed_roles
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean)
          : [],
        capabilities_json: {
          scheduler: true,
          guardrails: true,
        },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin", "data-sources"] });
      form.reset();
    },
  });

  const csvMutation = useMutation({
    mutationFn: async (values: z.infer<typeof csvSchema>) => {
      const file = values.file[0];
      const payload = new FormData();
      payload.append("file", file);
      if ((values.source_key || "").trim()) {
        payload.append("source_key", values.source_key!.trim());
      }
      if ((values.table_name || "").trim()) {
        payload.append("table_name", values.table_name!.trim());
      }
      payload.append("delimiter", values.delimiter);
      payload.append("auto_mode", String(values.auto_mode));
      payload.append("apply", String(values.apply));
      return api.autoConfigFromCsv(payload);
    },
  });

  const runWithCandidate = (candidate: CsvAutoResolutionCandidate) => {
    const values = csvForm.getValues();
    if (!values.file || values.file.length === 0) {
      return;
    }
    csvMutation.mutate({
      ...values,
      source_key: candidate.source_key,
      table_name: candidate.table_name,
      auto_mode: false,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Источники данных и адаптеры</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Ключ источника</Label>
              <Input {...form.register("key")} placeholder="taxi_prod" />
            </div>
            <div className="space-y-2">
              <Label>Диалект</Label>
              <Input {...form.register("dialect")} placeholder="postgres | mysql | clickhouse" />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Название</Label>
            <Input {...form.register("name")} placeholder="Боевая витрина заказов" />
          </div>

          <div className="space-y-2">
            <Label>Описание</Label>
            <Textarea rows={3} {...form.register("description")} placeholder="Для real-world подключения без переписывания semantic layer." />
          </div>

          <div className="space-y-2">
            <Label>Connection URL</Label>
            <Textarea rows={3} {...form.register("connection_url")} placeholder="postgresql+psycopg://..." />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Schema</Label>
              <Input {...form.register("schema_name")} placeholder="analytics" />
            </div>
            <div className="space-y-2">
              <Label>Роли с доступом</Label>
              <Input {...form.register("allowed_roles")} placeholder="admin, analyst, business_user" />
            </div>
          </div>

          {mutation.error ? <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-200">{mutation.error.message}</div> : null}

          <Button disabled={mutation.isPending}>{mutation.isPending ? "Сохраняем…" : "Добавить источник"}</Button>
        </form>

        <div className="space-y-3">
          <div className="rounded-2xl border border-border/80 bg-black/24 p-4">
            <div className="mb-3 text-sm font-medium">Автоконфиг semantic layer из CSV</div>
            <form className="space-y-3" onSubmit={csvForm.handleSubmit((values) => csvMutation.mutate(values))}>
              <div className="space-y-2">
                <Label>CSV-файл</Label>
                <Input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) => csvForm.setValue("file", event.target.files as FileList, { shouldValidate: true })}
                />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Delimiter</Label>
                  <Input {...csvForm.register("delimiter")} placeholder="auto | , | ; | tab" />
                </div>
                <div className="mt-7 space-y-2 text-sm text-muted-foreground">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={Boolean(csvForm.watch("auto_mode"))}
                      onChange={(event) => csvForm.setValue("auto_mode", event.target.checked)}
                    />
                    Безопасный авто-режим (рекомендуется)
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={Boolean(csvForm.watch("apply"))}
                      onChange={(event) => csvForm.setValue("apply", event.target.checked)}
                    />
                    Сразу применить новый каталог
                  </label>
                </div>
              </div>

              {!csvForm.watch("auto_mode") ? (
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Ключ источника</Label>
                    <Input {...csvForm.register("source_key")} placeholder="default" />
                  </div>
                  <div className="space-y-2">
                    <Label>Таблица в БД</Label>
                    <Input {...csvForm.register("table_name")} placeholder="analytics.order_tender_facts" />
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
                  Ручной ввод source_key/table_name отключен. Система выберет безопасные значения автоматически.
                </div>
              )}

              {csvMutation.error ? (
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-200">{csvMutation.error.message}</div>
              ) : null}

              <Button disabled={csvMutation.isPending}>{csvMutation.isPending ? "Обрабатываем…" : "Загрузить CSV и сгенерировать"}</Button>
            </form>

            {csvMutation.data ? (
              <div className="mt-4 space-y-2 rounded-xl border border-border/80 bg-black/30 p-3 text-xs text-muted-foreground">
                <div>
                  Статус: {csvMutation.data.applied ? "применено" : "черновик"} • Dataset: {csvMutation.data.catalog_preview.base_dataset}
                </div>
                <div>
                  Выбрано автоматически: {csvMutation.data.auto_resolution.resolved_source_key} / {csvMutation.data.auto_resolution.resolved_table_name}
                </div>
                <div>Определенный delimiter: {csvMutation.data.used_delimiter}</div>
                <div className={csvMutation.data.auto_resolution.validated ? "text-emerald-200" : "text-amber-200"}>
                  Проверка: {csvMutation.data.auto_resolution.validation_message || (csvMutation.data.auto_resolution.validated ? "OK" : "нужна ручная проверка")}
                </div>
                {csvMutation.data.auto_resolution.notes.length ? (
                  <div>Причина: {csvMutation.data.auto_resolution.notes.join(" ")}</div>
                ) : null}
                {csvMutation.data.auto_resolution.candidates.length ? (
                  <div className="rounded border border-border/70 p-2">
                    Варианты:
                    {csvMutation.data.auto_resolution.candidates.slice(0, 2).map((item) => (
                      <div key={`${item.source_key}:${item.table_name}`} className="mt-2 rounded border border-border/70 p-2">
                        <div>
                          {item.source_key} / {item.table_name} ({Math.round(item.confidence * 100)}%) — {item.reason}
                        </div>
                        <Button
                          type="button"
                          variant="secondary"
                          className="mt-2 h-7 px-2 text-xs"
                          disabled={csvMutation.isPending}
                          onClick={() => runWithCandidate(item)}
                        >
                          Применить этот вариант
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : null}
                <div>
                  Метрик: {csvMutation.data.catalog_preview.metrics_count} • Измерений: {csvMutation.data.catalog_preview.dimensions_count} • Фильтров:{" "}
                  {csvMutation.data.catalog_preview.filters_count}
                </div>
                <div className="max-h-36 overflow-auto rounded border border-border/70 p-2">
                  {csvMutation.data.catalog_preview.columns.slice(0, 12).map((column) => (
                    <div key={column.name}>
                      {column.name} — {column.inferred_type} (filled {Math.round(column.non_null_ratio * 100)}%)
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          {(data ?? []).map((source) => (
            <div key={source.id} className="rounded-2xl border border-border/80 bg-black/24 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="font-medium">{source.name}</div>
                <Badge variant={source.is_default ? "success" : "outline"}>{source.is_default ? "По умолчанию" : source.dialect}</Badge>
                {!source.is_active ? <Badge variant="secondary">Выключен</Badge> : null}
              </div>
              <div className="mt-2 text-sm text-muted-foreground">{source.description || "Описание не заполнено"}</div>
              <div className="mt-3 rounded-xl border border-border/80 bg-black/30 px-3 py-2 text-xs text-muted-foreground">
                {source.connection_url}
              </div>
              <div className="mt-3 text-xs text-muted-foreground">
                Ключ: {source.key} • Schema: {source.schema_name || "не задана"} • Роли: {source.allowed_roles_json.join(", ") || "все"}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
