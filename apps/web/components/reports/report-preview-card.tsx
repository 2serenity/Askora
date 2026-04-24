"use client";

import { BarChart3, LineChart as LineChartIcon } from "lucide-react";
import { type ReactNode, useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { type MetricKind, buildColumnLabels, formatAnalyticsValue, getChartTypeLabel, getMetricGroupLabel, getMetricKind } from "@/lib/presentation";
import { cn, formatNumber } from "@/lib/utils";
import type { QueryPlan } from "@/types/api";

const palette = ["#7aff4c", "#30e67f", "#bcff52", "#7de4b4"];
const gridStroke = "rgba(122, 255, 76, 0.12)";

type PreviewRow = Record<string, unknown>;
type PreviewData = {
  rows: PreviewRow[];
  columns: string[];
};

type MetricGroup = {
  id: string;
  label: string;
  keys: string[];
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asRows(value: unknown): PreviewRow[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is PreviewRow => Boolean(item) && typeof item === "object" && !Array.isArray(item));
}

function normalizeValue(value: unknown) {
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (/^-?\d+(?:\.\d+)?$/.test(trimmed)) {
      return Number(trimmed);
    }
    return formatAnalyticsValue(trimmed);
  }
  return value;
}

function normalizeRows(rows: PreviewRow[]) {
  return rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, normalizeValue(value)])));
}

function inferPreview(preview: unknown): PreviewData {
  const record = asRecord(preview);
  const rows = asRows(record.rows);
  const columns = Array.isArray(record.columns)
    ? record.columns.filter((item): item is string => typeof item === "string" && item.length > 0)
    : rows[0]
      ? Object.keys(rows[0])
      : [];
  return { rows, columns };
}

function detectMetricKeys(columns: string[], rows: PreviewRow[], queryPlan?: QueryPlan | null) {
  const queryMetrics = queryPlan?.metrics?.map((item) => item.key).filter((key) => columns.includes(key)) ?? [];
  if (queryMetrics.length) {
    return queryMetrics;
  }

  return columns.filter((column) =>
    rows.some((row) => {
      const value = normalizeValue(row[column]);
      return typeof value === "number" && Number.isFinite(value);
    }),
  );
}

function detectXAxis(columns: string[], metricKeys: string[], queryPlan?: QueryPlan | null) {
  const plannedDimension = queryPlan?.dimensions?.find((item) => columns.includes(item.key))?.key;
  if (plannedDimension) {
    return plannedDimension;
  }
  return columns.find((column) => !metricKeys.includes(column)) ?? null;
}

function buildMetricGroups(metricKeys: string[], chartType?: string | null, labels?: Record<string, string>) {
  if (!metricKeys.length) {
    return [] as MetricGroup[];
  }

  if (!["line", "bar"].includes(chartType ?? "")) {
    return [{ id: "primary", label: "Показатели", keys: metricKeys }];
  }

  const byKind = new Map<string, string[]>();
  metricKeys.forEach((key) => {
    const kind = getMetricKind(key);
    const current = byKind.get(kind) ?? [];
    current.push(key);
    byKind.set(kind, current);
  });

  if (byKind.size <= 1) {
    return [{ id: "primary", label: "Показатели", keys: metricKeys }];
  }

  return Array.from(byKind.entries()).map(([kind, keys]) => ({
    id: kind,
    label: keys.length === 1 ? labels?.[keys[0]] ?? keys[0] : getMetricGroupLabel(kind as MetricKind),
    keys,
  }));
}

function PreviewChart({
  chartType,
  rows,
  xKey,
  yKeys,
  labels,
  compact,
}: {
  chartType?: string | null;
  rows: PreviewRow[];
  xKey: string | null;
  yKeys: string[];
  labels: Record<string, string>;
  compact?: boolean;
}) {
  const normalizedRows = useMemo(() => normalizeRows(rows), [rows]);
  if (!xKey || !yKeys.length || !normalizedRows.length) {
    return null;
  }

  const heightClass = compact ? "h-[198px]" : "h-[248px]";

  return (
    <div className={heightClass}>
      <ResponsiveContainer width="100%" height="100%">
        {chartType === "bar" ? (
          <BarChart data={normalizedRows}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
            <XAxis dataKey={xKey} tick={{ fill: "#9ca79d", fontSize: 11 }} axisLine={{ stroke: gridStroke }} tickLine={false} />
            <YAxis tick={{ fill: "#9ca79d", fontSize: 11 }} axisLine={{ stroke: gridStroke }} tickLine={false} />
            <Tooltip
              formatter={(value) => formatNumber(value as number)}
              contentStyle={{ background: "#0d110d", border: "1px solid rgba(122,255,76,0.18)", borderRadius: "16px" }}
              labelStyle={{ color: "#ecf5e7" }}
            />
            {yKeys.map((key, index) => (
              <Bar key={key} dataKey={key} name={labels[key] ?? key} fill={palette[index % palette.length]} radius={[8, 8, 0, 0]} />
            ))}
          </BarChart>
        ) : (
          <LineChart data={normalizedRows}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
            <XAxis dataKey={xKey} tick={{ fill: "#9ca79d", fontSize: 11 }} axisLine={{ stroke: gridStroke }} tickLine={false} />
            <YAxis tick={{ fill: "#9ca79d", fontSize: 11 }} axisLine={{ stroke: gridStroke }} tickLine={false} />
            <Tooltip
              formatter={(value) => formatNumber(value as number)}
              contentStyle={{ background: "#0d110d", border: "1px solid rgba(122,255,76,0.18)", borderRadius: "16px" }}
              labelStyle={{ color: "#ecf5e7" }}
            />
            {yKeys.map((key, index) => (
              <Line key={key} type="monotone" dataKey={key} name={labels[key] ?? key} stroke={palette[index % palette.length]} strokeWidth={2.5} dot={false} />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

export function ReportPreviewCard({
  title,
  subtitle,
  question,
  chartType,
  metricLabels,
  periodLabel,
  preview,
  queryPlan,
  note,
  actions,
  compact = false,
  tone = "default",
}: {
  title: string;
  subtitle?: string;
  question?: string;
  chartType?: string | null;
  metricLabels?: string[];
  periodLabel?: string | null;
  preview?: unknown;
  queryPlan?: Record<string, unknown>;
  note?: string | null;
  actions?: ReactNode;
  compact?: boolean;
  tone?: "default" | "chat";
}) {
  const normalizedPlan = (queryPlan ?? null) as QueryPlan | null;
  const labels = buildColumnLabels(normalizedPlan);
  const previewData = useMemo(() => inferPreview(preview), [preview]);
  const metricKeys = useMemo(
    () => detectMetricKeys(previewData.columns, previewData.rows, normalizedPlan).slice(0, compact ? 4 : 6),
    [compact, normalizedPlan, previewData.columns, previewData.rows],
  );
  const xKey = useMemo(() => detectXAxis(previewData.columns, metricKeys, normalizedPlan), [metricKeys, normalizedPlan, previewData.columns]);
  const chartRows = useMemo(() => previewData.rows.slice(0, compact ? 8 : 12), [compact, previewData.rows]);
  const metricGroups = useMemo(() => buildMetricGroups(metricKeys, chartType, labels), [chartType, labels, metricKeys]);
  const tableColumns = useMemo(() => {
    const baseColumns = previewData.columns.length
      ? previewData.columns.slice(0, compact ? 4 : 5)
      : [xKey, ...metricKeys].filter((value): value is string => typeof value === "string" && value.length > 0);
    return baseColumns.slice(0, compact ? 4 : 5);
  }, [compact, metricKeys, previewData.columns, xKey]);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-[28px] border p-4 shadow-[0_18px_50px_rgba(0,0,0,0.2)]",
        tone === "chat" ? "border-primary/16 bg-black/35" : "border-border/80 bg-black/24",
        compact ? "space-y-3" : "space-y-4",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            {subtitle ? <Badge variant="secondary">{subtitle}</Badge> : null}
            {chartType ? <Badge variant="outline">{getChartTypeLabel(chartType)}</Badge> : null}
            {periodLabel ? <Badge variant="outline">{periodLabel}</Badge> : null}
          </div>
          <div className="text-base font-semibold text-foreground">{title}</div>
          {question ? <div className="text-sm text-muted-foreground">{question}</div> : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
      </div>

      {note ? <div className="rounded-2xl border border-border/70 bg-black/24 px-3 py-2 text-sm text-muted-foreground">{note}</div> : null}

      {metricLabels?.length ? (
        <div className="flex flex-wrap gap-2">
          {metricLabels.slice(0, compact ? 3 : 5).map((metric) => (
            <Badge key={metric} variant="outline">
              {metric}
            </Badge>
          ))}
        </div>
      ) : null}

      {metricGroups.length && xKey && ["line", "bar"].includes(chartType ?? "") ? (
        <div className={cn("grid gap-3", metricGroups.length > 1 && !compact ? "xl:grid-cols-2" : "grid-cols-1")}>
          {metricGroups.map((group, groupIndex) => (
            <div key={group.id} className="rounded-2xl border border-border/80 bg-black/18 p-3">
              {metricGroups.length > 1 ? (
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-foreground">
                  <LineChartIcon className="h-4 w-4 text-primary" />
                  {group.label}
                </div>
              ) : null}
              <PreviewChart chartType={chartType} rows={chartRows} xKey={xKey} yKeys={group.keys} labels={labels} compact={compact} />
              {metricGroups.length > 1 && groupIndex < metricGroups.length - 1 && compact ? <div className="mt-2 h-px bg-border/70" /> : null}
            </div>
          ))}
        </div>
      ) : metricKeys.length && previewData.rows[0] ? (
        <div className={cn("grid gap-3", compact ? "grid-cols-1" : "md:grid-cols-2 xl:grid-cols-4")}>
          {metricKeys.slice(0, compact ? 2 : 4).map((key) => (
            <div key={key} className="rounded-2xl border border-border/80 bg-black/18 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{labels[key] ?? key}</div>
              <div className="mt-2 text-2xl font-semibold text-foreground">{formatNumber(normalizeValue(previewData.rows[0]?.[key]) as number | string)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-2xl border border-border/70 bg-black/18 px-3 py-2 text-sm text-muted-foreground">
          <BarChart3 className="h-4 w-4" />
          Превью появится после первого сохранённого запуска отчёта.
        </div>
      )}

      {previewData.rows.length && tableColumns.length ? (
        <div className="overflow-hidden rounded-2xl border border-border/80 bg-black/18">
          <div
            className="grid border-b border-border/70 bg-black/28 text-xs uppercase tracking-[0.16em] text-muted-foreground"
            style={{ gridTemplateColumns: `repeat(${tableColumns.length}, minmax(0, 1fr))` }}
          >
            {tableColumns.map((column) => (
              <div key={column} className="px-3 py-2">
                {labels[column] ?? column}
              </div>
            ))}
          </div>
          <div className="divide-y divide-border/70">
            {previewData.rows.slice(0, compact ? 2 : 4).map((row, index) => (
              <div
                key={`${title}-${index}`}
                className="grid text-sm"
                style={{ gridTemplateColumns: `repeat(${tableColumns.length}, minmax(0, 1fr))` }}
              >
                {tableColumns.map((column) => (
                  <div key={column} className="truncate px-3 py-2 text-foreground/90">
                    {formatNumber(normalizeValue(row[column]) as number | string | null)}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
