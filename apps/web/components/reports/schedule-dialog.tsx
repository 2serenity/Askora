"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";

const weekdays = [
  { value: "1", label: "Понедельник" },
  { value: "2", label: "Вторник" },
  { value: "3", label: "Среда" },
  { value: "4", label: "Четверг" },
  { value: "5", label: "Пятница" },
  { value: "6", label: "Суббота" },
  { value: "0", label: "Воскресенье" },
];

const presets = [
  { label: "Понедельник 09:00", cadence: "weekly", weekday: "1", send_time: "09:00" },
  { label: "Будни 08:30", cadence: "weekdays", weekday: "1", send_time: "08:30" },
  { label: "Каждый день 18:00", cadence: "daily", weekday: "1", send_time: "18:00" },
];

const schema = z
  .object({
    mode: z.enum(["simple", "advanced"]).default("simple"),
    cadence: z.enum(["weekly", "weekdays", "daily"]).default("weekly"),
    weekday: z.string().default("1"),
    send_time: z.string().regex(/^([01]\d|2[0-3]):([0-5]\d)$/, "Введите время в формате ЧЧ:ММ"),
    cron_expression: z.string().min(5, "Нужен cron-формат"),
    timezone: z.string().min(2, "Укажите часовой пояс"),
    channel: z.enum(["email", "group"]).default("email"),
    recipient: z.string().optional(),
    target_group_id: z.string().optional(),
  })
  .superRefine((value, ctx) => {
    if (value.channel === "email" && !value.recipient?.trim()) {
      ctx.addIssue({ code: "custom", path: ["recipient"], message: "Укажите email получателя" });
    }
    if (value.channel === "group" && !value.target_group_id) {
      ctx.addIssue({ code: "custom", path: ["target_group_id"], message: "Выберите рабочую группу" });
    }
  });

function buildCronExpression(cadence: "weekly" | "weekdays" | "daily", weekday: string, sendTime: string) {
  const [hours, minutes] = sendTime.split(":");
  const hour = Number(hours);
  const minute = Number(minutes);

  if (cadence === "daily") {
    return `${minute} ${hour} * * *`;
  }
  if (cadence === "weekdays") {
    return `${minute} ${hour} * * 1-5`;
  }
  return `${minute} ${hour} * * ${weekday}`;
}

function buildHumanSummary(cadence: "weekly" | "weekdays" | "daily", weekday: string, sendTime: string, timezone: string) {
  if (cadence === "daily") {
    return `Каждый день в ${sendTime} (${timezone})`;
  }
  if (cadence === "weekdays") {
    return `По будням в ${sendTime} (${timezone})`;
  }
  const weekdayLabel = weekdays.find((item) => item.value === weekday)?.label ?? "выбранный день";
  return `Каждый ${weekdayLabel.toLowerCase()} в ${sendTime} (${timezone})`;
}

export function ScheduleDialog({ reportId }: { reportId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const groups = useQuery({
    queryKey: ["groups"],
    queryFn: api.groups,
    enabled: open,
  });

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      mode: "simple",
      cadence: "weekly",
      weekday: "1",
      send_time: "09:00",
      cron_expression: "0 9 * * 1",
      timezone: "Europe/Kaliningrad",
      channel: "email",
      recipient: "demo@example.com",
      target_group_id: "",
    },
  });

  const mode = form.watch("mode");
  const cadence = form.watch("cadence");
  const weekday = form.watch("weekday");
  const sendTime = form.watch("send_time");
  const timezone = form.watch("timezone");
  const channel = form.watch("channel");

  useEffect(() => {
    if (mode !== "simple") {
      return;
    }
    form.setValue("cron_expression", buildCronExpression(cadence, weekday, sendTime), { shouldValidate: true });
  }, [cadence, form, mode, sendTime, weekday]);

  const humanSummary = useMemo(() => buildHumanSummary(cadence, weekday, sendTime, timezone), [cadence, sendTime, timezone, weekday]);

  const mutation = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      api.createSchedule(reportId, {
        cron_expression: values.cron_expression,
        timezone: values.timezone.trim(),
        recipient: values.channel === "email" ? values.recipient?.trim() || null : null,
        channel: values.channel,
        target_group_id: values.channel === "group" ? values.target_group_id || null : null,
        is_active: true,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["schedules"] });
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["report", reportId] });
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      setOpen(false);
    },
  });

  function applyPreset(preset: (typeof presets)[number]) {
    form.setValue("cadence", preset.cadence as "weekly" | "weekdays" | "daily");
    form.setValue("weekday", preset.weekday);
    form.setValue("send_time", preset.send_time);
    form.setValue(
      "cron_expression",
      buildCronExpression(preset.cadence as "weekly" | "weekdays" | "daily", preset.weekday, preset.send_time),
      { shouldValidate: true },
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) {
          form.reset();
          mutation.reset();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button variant="secondary">Запланировать</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Настроить расписание</DialogTitle>
          <DialogDescription>
            Пример для отправки отчёта: каждый понедельник в 09:00, часовой пояс `Europe/Kaliningrad`, канал email или рабочая группа.
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-5" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <Tabs value={mode} onValueChange={(value) => form.setValue("mode", value as "simple" | "advanced")}>
            <TabsList className="mt-2 grid w-full grid-cols-2">
              <TabsTrigger value="simple">Простой режим</TabsTrigger>
              <TabsTrigger value="advanced">Cron</TabsTrigger>
            </TabsList>

            <TabsContent value="simple" className="space-y-4">
              <div className="space-y-2">
                <Label>Быстрые шаблоны</Label>
                <div className="flex flex-wrap gap-2">
                  {presets.map((preset) => (
                    <Button key={preset.label} type="button" variant="outline" size="sm" onClick={() => applyPreset(preset)}>
                      {preset.label}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Когда отправлять</Label>
                  <Controller
                    control={form.control}
                    name="cadence"
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="weekly">Раз в неделю</SelectItem>
                          <SelectItem value="weekdays">По будням</SelectItem>
                          <SelectItem value="daily">Каждый день</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>

                {cadence === "weekly" ? (
                  <div className="space-y-2">
                    <Label>День отправки</Label>
                    <Controller
                      control={form.control}
                      name="weekday"
                      render={({ field }) => (
                        <Select value={field.value} onValueChange={field.onChange}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {weekdays.map((day) => (
                              <SelectItem key={day.value} value={day.value}>
                                {day.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </div>
                ) : null}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="send-time">Время отправки</Label>
                  <Input id="send-time" type="time" {...form.register("send_time")} />
                  {form.formState.errors.send_time ? <div className="text-sm text-rose-300">{form.formState.errors.send_time.message}</div> : null}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="timezone">Часовой пояс</Label>
                  <Input id="timezone" {...form.register("timezone")} />
                  <div className="text-xs text-muted-foreground">Например: `Europe/Kaliningrad` или `Europe/Moscow`.</div>
                </div>
              </div>

              <div className="rounded-2xl border border-primary/18 bg-primary/8 p-4 text-sm">
                <div className="font-medium text-foreground">Что получится</div>
                <div className="mt-1 text-muted-foreground">{humanSummary}</div>
                <div className="mt-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">Сформированный cron</div>
                <div className="mt-2 rounded-xl border border-border/80 bg-black/30 px-3 py-2 font-mono text-sm">
                  {form.watch("cron_expression")}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="advanced" className="space-y-2">
              <Label htmlFor="cron">Расписание (cron)</Label>
              <Input id="cron" {...form.register("cron_expression")} />
              <div className="text-xs text-muted-foreground">Пример: `0 9 * * 1` означает отправку каждый понедельник в 09:00.</div>
              {form.formState.errors.cron_expression ? <div className="text-sm text-rose-300">{form.formState.errors.cron_expression.message}</div> : null}
            </TabsContent>
          </Tabs>

          <div className="space-y-2">
            <Label>Куда отправлять</Label>
            <Controller
              control={form.control}
              name="channel"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="email">На email</SelectItem>
                    <SelectItem value="group">В рабочую группу</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {channel === "email" ? (
            <div className="space-y-2">
              <Label htmlFor="recipient">Получатель</Label>
              <Input id="recipient" {...form.register("recipient")} />
              <div className="text-xs text-muted-foreground">Для демо можно оставить `demo@example.com`.</div>
              {form.formState.errors.recipient ? <div className="text-sm text-rose-300">{form.formState.errors.recipient.message}</div> : null}
            </div>
          ) : (
            <div className="space-y-2">
              <Label>Рабочая группа</Label>
              <Controller
                control={form.control}
                name="target_group_id"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите группу" />
                    </SelectTrigger>
                    <SelectContent>
                      {(groups.data ?? []).map((group) => (
                        <SelectItem key={group.id} value={group.id}>
                          {group.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              <div className="text-xs text-muted-foreground">После срабатывания расписания отчёт появится в чате выбранной группы.</div>
              {form.formState.errors.target_group_id ? <div className="text-sm text-rose-300">{form.formState.errors.target_group_id.message}</div> : null}
            </div>
          )}

          {mutation.error ? <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-200">{mutation.error.message}</div> : null}

          <Button className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Сохраняем…" : "Создать расписание"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
