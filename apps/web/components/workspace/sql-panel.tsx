import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyablePre } from "@/components/ui/copyable-pre";
import type { ValidationResult } from "@/types/api";

function SqlDetails({ sql, validation }: { sql: string; validation: ValidationResult }) {
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Badge variant={validation.allowed ? "success" : "danger"}>
          {validation.allowed ? "Разрешён" : "Заблокирован"}
        </Badge>
        <Badge variant="outline">Сложность {validation.complexity_score}</Badge>
        <Badge variant="outline">Лимит строк {validation.row_limit_applied}</Badge>
        {validation.estimated_cost !== null && validation.estimated_cost !== undefined ? (
          <Badge variant="outline">План cost {validation.estimated_cost.toFixed(2)}</Badge>
        ) : null}
        {validation.estimated_rows !== null && validation.estimated_rows !== undefined ? (
          <Badge variant="outline">План rows {Math.round(validation.estimated_rows)}</Badge>
        ) : null}
      </div>
      <CopyablePre
        value={sql || "SQL ещё не сгенерирован"}
        preClassName="overflow-x-auto rounded-2xl border border-primary/14 bg-black p-4 text-sm text-slate-100"
      />
      {!!validation.warnings.length && (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-200">
          {validation.warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      )}
      {!!validation.blocked_reasons.length && (
        <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">
          {validation.blocked_reasons.map((reason) => (
            <div key={reason}>{reason}</div>
          ))}
        </div>
      )}
    </>
  );
}

export function SqlPanel({
  sql,
  validation,
  embedded = false,
}: {
  sql: string;
  validation: ValidationResult;
  embedded?: boolean;
}) {
  if (embedded) {
    return (
      <div className="space-y-4 border-t border-border/80 pt-5">
        <div>
          <div className="text-sm font-medium text-foreground">SQL</div>
          <div className="mt-1 text-sm text-muted-foreground">
            Запрос собирается из плана и проходит проверку до выполнения.
          </div>
        </div>
        <SqlDetails sql={sql} validation={validation} />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <CardTitle>Построенный SQL</CardTitle>
          <CardDescription>SQL собирается только из плана запроса и проходит предварительную проверку перед выполнением.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <SqlDetails sql={sql} validation={validation} />
      </CardContent>
    </Card>
  );
}
