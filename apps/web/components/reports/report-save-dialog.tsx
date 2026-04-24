"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { QueryResult } from "@/types/api";

const schema = z.object({
  name: z.string().min(3, "Минимум 3 символа"),
  description: z.string().optional(),
});

export function ReportSaveDialog({
  result,
  onSaved,
}: {
  result: QueryResult;
  onSaved: (reportId: string) => void;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: result.question,
      description: "",
    },
  });

  useEffect(() => {
    form.reset({
      name: result.question,
      description: "",
    });
  }, [form, result.question]);

  const mutation = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      api.saveReport({
        name: values.name.trim(),
        description: values.description?.trim() || "",
        question: result.question,
        query_plan_json: result.query_plan,
        sql_text: result.generated_sql,
        chart_type: result.visualization.chart_type,
        row_count: result.row_count,
        execution_status: result.status,
        result_preview_json: {
          rows: result.rows.slice(0, 20),
          columns: result.columns,
        },
      }),
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      onSaved(saved.id);
      setOpen(false);
    },
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) {
          form.reset({
            name: result.question,
            description: "",
          });
          mutation.reset();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button>Сохранить отчёт</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Сохранить отчёт</DialogTitle>
          <DialogDescription>
            Отчёт появится в каталоге и сможет запускаться повторно или по расписанию. Если такой отчёт уже сохранён, система обновит его, а не создаст дубль.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <div className="space-y-2">
            <Label htmlFor="report-name">Название</Label>
            <Input id="report-name" {...form.register("name")} />
            {form.formState.errors.name ? <div className="text-sm text-rose-300">{form.formState.errors.name.message}</div> : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="report-description">Описание</Label>
            <Textarea id="report-description" rows={4} {...form.register("description")} />
          </div>

          {mutation.error ? <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-200">{mutation.error.message}</div> : null}

          <Button className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Сохраняем…" : "Сохранить"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
