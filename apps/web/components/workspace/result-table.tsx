import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatNumber } from "@/lib/utils";
import { buildColumnLabels, formatAnalyticsValue } from "@/lib/presentation";
import type { QueryPlan } from "@/types/api";

export function ResultTable({
  columns,
  rows,
  plan,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
  plan?: QueryPlan;
}) {
  const labels = buildColumnLabels(plan);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Табличный результат</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length ? (
          <Table>
            <TableHeader>
              <TableRow>
                {columns.map((column) => (
                  <TableHead key={column}>{labels[column] ?? column}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row, index) => (
                <TableRow key={index}>
                  {columns.map((column) => (
                    <TableCell key={column}>
                      {formatNumber((typeof row[column] === "string" ? formatAnalyticsValue(row[column]) : row[column]) as number | string | null)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div className="rounded-2xl border border-border/80 bg-black/24 p-6 text-sm text-muted-foreground">
            Нет данных для отображения. Либо запрос был заблокирован, либо вернул пустой результат.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
