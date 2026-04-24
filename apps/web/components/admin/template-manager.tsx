"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

const schema = z.object({
  name: z.string().min(3),
  description: z.string().min(3),
  pattern: z.string().min(3),
  guidance: z.string().min(3),
  example_question: z.string().min(3)
});

export function TemplateManager() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["admin", "templates"],
    queryFn: api.templates
  });
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      description: "",
      pattern: "",
      guidance: "",
      example_question: ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      api.createTemplate({
        ...values,
        output_shape_json: { chart: "bar" },
        owner_role: "analyst",
        is_active: true
      }),
    onSuccess: async () => {
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["admin", "templates"] });
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Шаблоны запросов</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <div className="space-y-2">
            <Label>Название</Label>
            <Input {...form.register("name")} />
          </div>
          <div className="space-y-2">
            <Label>Описание</Label>
            <Textarea rows={3} {...form.register("description")} />
          </div>
          <div className="space-y-2">
            <Label>Шаблон вопроса</Label>
            <Input {...form.register("pattern")} />
          </div>
          <div className="space-y-2">
            <Label>Подсказка для генератора</Label>
            <Textarea rows={3} {...form.register("guidance")} />
          </div>
          <div className="space-y-2">
            <Label>Пример вопроса</Label>
            <Input {...form.register("example_question")} />
          </div>
          <Button disabled={mutation.isPending}>{mutation.isPending ? "Сохраняем…" : "Добавить шаблон"}</Button>
        </form>
        <div className="space-y-3">
          {(data ?? []).map((template) => (
            <div key={template.id} className="rounded-2xl border border-border/80 bg-black/24 p-4">
              <div className="font-medium">{template.name}</div>
              <div className="mt-1 text-sm text-muted-foreground">{template.description}</div>
              <div className="mt-2 text-xs text-muted-foreground">{template.pattern}</div>
              <div className="mt-2 text-xs text-muted-foreground">{template.example_question}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
