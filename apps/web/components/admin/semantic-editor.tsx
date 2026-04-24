"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

const schema = z.object({
  term: z.string().min(2),
  entity_type: z.string().min(2),
  target_key: z.string().min(2),
  synonyms_json: z.string().optional(),
  description: z.string().optional()
});

export function SemanticEditor() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["admin", "semantic-entries"],
    queryFn: api.semanticEntries
  });
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      term: "",
      entity_type: "metric",
      target_key: "",
      synonyms_json: "",
      description: ""
    }
  });
  const mutation = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      api.createSemanticEntry({
        term: values.term,
        entity_type: values.entity_type,
        target_key: values.target_key,
        synonyms_json: values.synonyms_json ? values.synonyms_json.split(",").map((item) => item.trim()) : [],
        description: values.description,
        is_active: true
      }),
    onSuccess: async () => {
      form.reset();
      await queryClient.invalidateQueries({ queryKey: ["admin", "semantic-entries"] });
    }
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Семантический слой: словарь и синонимы</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <div className="space-y-2">
            <Label>Термин</Label>
            <Input {...form.register("term")} placeholder="например, канал привлечения" />
          </div>
          <div className="space-y-2">
            <Label>Тип сущности</Label>
            <Input {...form.register("entity_type")} placeholder="metric | dimension | filter" />
          </div>
          <div className="space-y-2">
            <Label>Ключ в словаре</Label>
            <Input {...form.register("target_key")} placeholder="channel" />
          </div>
          <div className="space-y-2">
            <Label>Синонимы</Label>
            <Input {...form.register("synonyms_json")} placeholder="источник заказа, маркетинговый канал" />
          </div>
          <div className="space-y-2">
            <Label>Описание</Label>
            <Input {...form.register("description")} placeholder="Расширение словаря для пользователей" />
          </div>
          <Button disabled={mutation.isPending}>{mutation.isPending ? "Сохраняем…" : "Добавить термин"}</Button>
        </form>
        <div className="space-y-3">
          {(data ?? []).map((entry) => (
            <div key={entry.id} className="rounded-2xl border border-border/80 bg-black/24 p-4">
              <div className="font-medium">{entry.term}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {entry.entity_type} → {entry.target_key}
              </div>
              <div className="mt-2 text-xs text-muted-foreground">{entry.synonyms_json.join(", ")}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
