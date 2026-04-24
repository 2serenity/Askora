"use client";

import { BarChart3, Download, LineChart, Maximize2, PieChart as PieChartIcon, TableProperties } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Brush,
  CartesianGrid,
  Legend,
  Line,
  LineChart as RechartsLineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  buildColumnLabels,
  formatAnalyticsValue,
  getMetricGroupLabel,
  getMetricKind,
  type MetricKind,
} from "@/lib/presentation";
import { downloadCsv, formatNumber } from "@/lib/utils";
import type { QueryResult } from "@/types/api";

const palette = ["#7aff4c", "#27d86d", "#bcff52", "#e0ff8a", "#5fe7a1", "#d5ff6c"];
const chartStroke = "rgba(122, 255, 76, 0.14)";

type ChartType = QueryResult["visualization"]["chart_type"];

type ChartGroup = {
  id: string;
  kind: MetricKind;
  label: string;
  keys: string[];
};

function normalizeChartValue(value: unknown) {
  if (typeof value === "string") {
    if (/^-?\d+(?:\.\d+)?$/.test(value)) {
      return Number(value);
    }
    return formatAnalyticsValue(value);
  }
  return value;
}

function normalizeChartData(rows: Record<string, unknown>[]) {
  return rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, normalizeChartValue(value)])));
}

function aggregateMetricValue(rows: Record<string, unknown>[], metricKey: string) {
  const kind = getMetricKind(metricKey);
  const numericValues = rows
    .map((row) => normalizeChartValue(row[metricKey]))
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));

  if (!numericValues.length) {
    return rows.find((row) => row[metricKey] !== null && row[metricKey] !== undefined)?.[metricKey] ?? null;
  }

  const total = numericValues.reduce((sum, value) => sum + value, 0);
  if (kind === "count" || kind === "currency") {
    return total;
  }

  return total / numericValues.length;
}

function buildChartGroups(result: QueryResult) {
  const labels = buildColumnLabels(result.query_plan);
  const metricKeys = result.visualization.y_keys;
  const chartType = result.visualization.chart_type;

  if (!["line", "bar", "area"].includes(chartType) || metricKeys.length <= 1) {
    return [
      {
        id: "primary",
        kind: metricKeys[0] ? getMetricKind(metricKeys[0]) : "other",
        label: result.visualization.title,
        keys: metricKeys,
      },
    ] satisfies ChartGroup[];
  }

  const grouped = new Map<MetricKind, string[]>();
  metricKeys.forEach((key) => {
    const kind = getMetricKind(key);
    const current = grouped.get(kind) ?? [];
    current.push(key);
    grouped.set(kind, current);
  });

  if (grouped.size <= 1) {
    return [
      {
        id: "primary",
        kind: getMetricKind(metricKeys[0] ?? ""),
        label: result.visualization.title,
        keys: metricKeys,
      },
    ] satisfies ChartGroup[];
  }

  return Array.from(grouped.entries()).map(([kind, keys]) => ({
    id: kind,
    kind,
    label: keys.length === 1 ? labels[keys[0]] ?? keys[0] : getMetricGroupLabel(kind),
    keys,
  }));
}

function getAvailableChartTypes(result: QueryResult): ChartType[] {
  const hasXAxis = Boolean(result.visualization.x_key);
  const hasRows = result.rows.length > 0;
  const metricCount = result.visualization.y_keys.length;
  if (!hasRows) {
    return [];
  }

  const types: ChartType[] = [];
  if (hasXAxis) {
    types.push("line", "bar", "area");
  }
  if (hasXAxis && metricCount === 1) {
    types.push("pie");
  }
  types.push("kpi", "table");
  return Array.from(new Set(types));
}

function getChartTypeLabel(type: ChartType) {
  const labels: Record<ChartType, string> = {
    line: "Линия",
    bar: "Столбцы",
    pie: "Круг",
    area: "Область",
    kpi: "Карточки",
    table: "Таблица",
  };
  return labels[type];
}

function ChartDataTable({ result }: { result: QueryResult }) {
  const labels = buildColumnLabels(result.query_plan);
  const displayColumns = result.columns.length
    ? result.columns
    : ([result.visualization.x_key, ...result.visualization.y_keys].filter(Boolean) as string[]);

  return (
    <div className="max-h-[260px] overflow-auto rounded-2xl border border-border/80 bg-black/18">
      <Table>
        <TableHeader>
          <TableRow>
            {displayColumns.map((column) => (
              <TableHead key={column}>{labels[column] ?? column}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {result.rows.slice(0, 150).map((row, index) => (
            <TableRow key={`${index}-${displayColumns.join("-")}`}>
              {displayColumns.map((column) => (
                <TableCell key={column}>{formatNumber(normalizeChartValue(row[column]) as number | string | null)}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ChartCanvas({
  result,
  metricKeys,
  expanded = false,
}: {
  result: QueryResult;
  metricKeys: string[];
  expanded?: boolean;
}) {
  const { visualization, rows } = result;
  const labels = buildColumnLabels(result.query_plan);
  const chartData = useMemo(() => normalizeChartData(rows), [rows]);
  const heightClass = expanded ? "h-[520px]" : "h-[320px]";

  if (!rows.length) {
    return <div className="text-sm text-muted-foreground">График появится после успешного выполнения запроса.</div>;
  }

  if (!metricKeys.length) {
    return <div className="text-sm text-muted-foreground">Все линии скрыты. Включите хотя бы одну метрику.</div>;
  }

  if (visualization.chart_type === "table") {
    return <ChartDataTable result={result} />;
  }

  if (visualization.chart_type === "line" && visualization.x_key) {
    return (
      <div className={heightClass}>
        <ResponsiveContainer width="100%" height="100%">
          <RechartsLineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartStroke} />
            <XAxis
              dataKey={visualization.x_key}
              tick={{ fill: "#98a19a", fontSize: 12 }}
              axisLine={{ stroke: chartStroke }}
              tickLine={{ stroke: chartStroke }}
            />
            <YAxis tick={{ fill: "#98a19a", fontSize: 12 }} axisLine={{ stroke: chartStroke }} tickLine={{ stroke: chartStroke }} />
            <Tooltip
              formatter={(value) => formatNumber(value as number)}
              contentStyle={{ background: "#0d110d", border: "1px solid rgba(122,255,76,0.18)", borderRadius: "16px" }}
              labelStyle={{ color: "#ecf5e7" }}
              itemStyle={{ color: "#ecf5e7" }}
            />
            <Legend />
            {metricKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                name={labels[key] ?? key}
                stroke={palette[index % palette.length]}
                strokeWidth={3}
                dot={false}
              />
            ))}
            {expanded ? <Brush dataKey={visualization.x_key} height={26} stroke={palette[0]} travellerWidth={12} /> : null}
          </RechartsLineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (visualization.chart_type === "area" && visualization.x_key) {
    return (
      <div className={heightClass}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartStroke} />
            <XAxis
              dataKey={visualization.x_key}
              tick={{ fill: "#98a19a", fontSize: 12 }}
              axisLine={{ stroke: chartStroke }}
              tickLine={{ stroke: chartStroke }}
            />
            <YAxis tick={{ fill: "#98a19a", fontSize: 12 }} axisLine={{ stroke: chartStroke }} tickLine={{ stroke: chartStroke }} />
            <Tooltip
              formatter={(value) => formatNumber(value as number)}
              contentStyle={{ background: "#0d110d", border: "1px solid rgba(122,255,76,0.18)", borderRadius: "16px" }}
              labelStyle={{ color: "#ecf5e7" }}
              itemStyle={{ color: "#ecf5e7" }}
            />
            <Legend />
            {metricKeys.map((key, index) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                name={labels[key] ?? key}
                stroke={palette[index % palette.length]}
                fill={palette[index % palette.length]}
                fillOpacity={0.18}
                strokeWidth={2.5}
              />
            ))}
            {expanded ? <Brush dataKey={visualization.x_key} height={26} stroke={palette[0]} travellerWidth={12} /> : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (visualization.chart_type === "bar" && visualization.x_key) {
    return (
      <div className={heightClass}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={chartStroke} />
            <XAxis
              dataKey={visualization.x_key}
              tick={{ fill: "#98a19a", fontSize: 12 }}
              axisLine={{ stroke: chartStroke }}
              tickLine={{ stroke: chartStroke }}
            />
            <YAxis tick={{ fill: "#98a19a", fontSize: 12 }} axisLine={{ stroke: chartStroke }} tickLine={{ stroke: chartStroke }} />
            <Tooltip
              formatter={(value) => formatNumber(value as number)}
              contentStyle={{ background: "#0d110d", border: "1px solid rgba(122,255,76,0.18)", borderRadius: "16px" }}
              labelStyle={{ color: "#ecf5e7" }}
              itemStyle={{ color: "#ecf5e7" }}
            />
            <Legend />
            {metricKeys.map((key, index) => (
              <Bar key={key} dataKey={key} name={labels[key] ?? key} fill={palette[index % palette.length]} radius={[10, 10, 0, 0]} />
            ))}
            {expanded ? <Brush dataKey={visualization.x_key} height={26} stroke={palette[0]} travellerWidth={12} /> : null}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (visualization.chart_type === "pie" && metricKeys[0] && visualization.x_key) {
    return (
      <div className={heightClass}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={chartData} dataKey={metricKeys[0]} nameKey={visualization.x_key} outerRadius={expanded ? 160 : 110} fill={palette[0]} />
            <Tooltip
              formatter={(value) => formatNumber(value as number)}
              contentStyle={{ background: "#0d110d", border: "1px solid rgba(122,255,76,0.18)", borderRadius: "16px" }}
              labelStyle={{ color: "#ecf5e7" }}
              itemStyle={{ color: "#ecf5e7" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (visualization.chart_type === "kpi") {
    return (
      <div className="grid gap-4 md:grid-cols-3">
        {metricKeys.map((key) => (
          <div key={key} className="rounded-2xl border border-border/80 bg-black/24 p-5">
            <div className="text-sm text-muted-foreground">{labels[key] ?? key}</div>
            <div className="mt-3 text-3xl font-semibold">{formatNumber(aggregateMetricValue(rows, key) as number | string | null)}</div>
          </div>
        ))}
      </div>
    );
  }

  return <div className="text-sm text-muted-foreground">Для этого запроса график недоступен.</div>;
}

function ChartGroupBlock({
  result,
  group,
  hiddenSeries,
  onToggleSeries,
  expanded = false,
}: {
  result: QueryResult;
  group: ChartGroup;
  hiddenSeries: Record<string, boolean>;
  onToggleSeries: (key: string) => void;
  expanded?: boolean;
}) {
  const labels = buildColumnLabels(result.query_plan);
  const activeKeys = group.keys.filter((key) => !hiddenSeries[key]);
  const canToggleSeries = ["line", "bar", "area"].includes(result.visualization.chart_type);

  return (
    <div className="rounded-2xl border border-border/80 bg-black/14 p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium">{group.label}</div>
          {result.visualization.y_keys.length > group.keys.length ? (
            <div className="mt-1 text-xs text-muted-foreground">Метрики этого типа показаны отдельно, чтобы шкала оставалась читаемой.</div>
          ) : null}
        </div>
        {canToggleSeries ? (
          <div className="flex flex-wrap gap-2">
            {group.keys.map((key) => {
              const isHidden = hiddenSeries[key];
              return (
                <Button key={key} variant={isHidden ? "ghost" : "outline"} size="sm" onClick={() => onToggleSeries(key)}>
                  {isHidden ? "Показать" : "Скрыть"} {labels[key] ?? key}
                </Button>
              );
            })}
          </div>
        ) : null}
      </div>
      <ChartCanvas result={result} metricKeys={activeKeys} expanded={expanded} />
    </div>
  );
}

export function ChartPanel({
  result,
  onChartTypeChange,
}: {
  result: QueryResult;
  onChartTypeChange?: (type: ChartType) => void;
}) {
  const [open, setOpen] = useState(false);
  const [hiddenSeries, setHiddenSeries] = useState<Record<string, boolean>>({});
  const hasRows = result.rows.length > 0;
  const chartGroups = useMemo(() => buildChartGroups(result), [result]);
  const availableChartTypes = useMemo(() => getAvailableChartTypes(result), [result]);

  function toggleSeries(key: string) {
    setHiddenSeries((current) => ({
      ...current,
      [key]: !current[key],
    }));
  }

  return (
    <Card>
      <CardHeader className="gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <CardTitle>{result.visualization.title}</CardTitle>
          <CardDescription>{result.visualization.description}</CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          {hasRows && onChartTypeChange ? (
            <div className="flex flex-wrap gap-2">
              {availableChartTypes.map((type) => {
                const icon =
                  type === "line" ? (
                    <LineChart className="mr-2 h-4 w-4" />
                  ) : type === "bar" || type === "area" || type === "kpi" ? (
                    <BarChart3 className="mr-2 h-4 w-4" />
                  ) : type === "pie" ? (
                    <PieChartIcon className="mr-2 h-4 w-4" />
                  ) : (
                    <TableProperties className="mr-2 h-4 w-4" />
                  );
                return (
                  <Button
                    key={type}
                    variant={result.visualization.chart_type === type ? "default" : "outline"}
                    size="sm"
                    onClick={() => onChartTypeChange(type)}
                  >
                    {icon}
                    {getChartTypeLabel(type)}
                  </Button>
                );
              })}
            </div>
          ) : null}
          {hasRows ? (
            <Button variant="outline" size="sm" onClick={() => downloadCsv("chart-data.csv", result.rows)}>
              <Download className="mr-2 h-4 w-4" />
              Скачать CSV
            </Button>
          ) : null}
          {hasRows ? (
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button variant="secondary" size="sm">
                  <Maximize2 className="mr-2 h-4 w-4" />
                  Открыть отдельно
                </Button>
              </DialogTrigger>
              <DialogContent className="max-h-[90vh] max-w-[min(1400px,96vw)] overflow-auto">
                <DialogHeader>
                  <DialogTitle>{result.visualization.title}</DialogTitle>
                  <DialogDescription>
                    Отдельный режим просмотра: увеличенный график, выбор диапазона на временной шкале и данные для ручной проверки.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-5">
                  <div className={`grid gap-4 ${chartGroups.length > 1 ? "xl:grid-cols-2" : ""}`}>
                    {chartGroups.map((group) => (
                      <ChartGroupBlock
                        key={group.id}
                        result={result}
                        group={group}
                        hiddenSeries={hiddenSeries}
                        onToggleSeries={toggleSeries}
                        expanded
                      />
                    ))}
                  </div>
                  <div className="space-y-3">
                    <div className="text-sm font-medium text-foreground">Данные графика</div>
                    <ChartDataTable result={result} />
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        <div className={`grid gap-4 ${chartGroups.length > 1 ? "xl:grid-cols-2" : ""}`}>
          {chartGroups.map((group) => (
            <ChartGroupBlock
              key={group.id}
              result={result}
              group={group}
              hiddenSeries={hiddenSeries}
              onToggleSeries={toggleSeries}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
