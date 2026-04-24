"use client";

import Link from "next/link";
import { ExternalLink, Play } from "lucide-react";

import { ReportPreviewCard } from "@/components/reports/report-preview-card";
import { Button } from "@/components/ui/button";

export function ReportMessageCard({
  title,
  question,
  reportId,
  chartType,
  metricLabels,
  periodLabel,
  preview,
  queryPlan,
  note,
  compact = false,
  kindLabel,
}: {
  title: string;
  question?: string;
  reportId?: string | null;
  chartType?: string | null;
  metricLabels?: string[];
  periodLabel?: string | null;
  preview?: unknown;
  queryPlan?: Record<string, unknown>;
  note?: string | null;
  compact?: boolean;
  kindLabel?: string;
}) {
  const actions = reportId ? (
    <>
      <Button asChild variant="outline" size="sm">
        <Link href={`/reports/${reportId}`}>
          <ExternalLink className="mr-2 h-4 w-4" />
          Открыть
        </Link>
      </Button>
      {question ? (
        <Button asChild variant="ghost" size="sm">
          <Link href={`/workspace?question=${encodeURIComponent(question)}`}>
            <Play className="mr-2 h-4 w-4" />
            Повторить
          </Link>
        </Button>
      ) : null}
    </>
  ) : null;

  return (
    <ReportPreviewCard
      title={title}
      subtitle={kindLabel ?? "Отчёт"}
      question={question}
      chartType={chartType}
      metricLabels={metricLabels}
      periodLabel={periodLabel}
      preview={preview}
      queryPlan={queryPlan}
      note={note}
      actions={actions}
      compact={compact}
      tone="chat"
    />
  );
}
