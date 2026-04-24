"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, Share2, Users2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";

export function ReportShareDialog({
  reportId,
  reportName,
  triggerLabel = "Поделиться отчётом",
  triggerVariant = "outline",
}: {
  reportId: string;
  reportName: string;
  triggerLabel?: string;
  triggerVariant?: "default" | "secondary" | "ghost" | "outline" | "danger";
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [origin, setOrigin] = useState("http://localhost:3000");
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [note, setNote] = useState("");

  const groups = useQuery({
    queryKey: ["groups"],
    queryFn: api.groups,
    enabled: open,
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      setOrigin(window.location.origin);
    }
  }, []);

  const shareToGroup = useMutation({
    mutationFn: () => api.shareReportToGroup(reportId, { group_id: selectedGroupId, note: note.trim() || undefined }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["report", reportId] });
      setOpen(false);
      setSelectedGroupId("");
      setNote("");
    },
  });

  const reportUrl = useMemo(() => `${origin}/reports/${reportId}`, [origin, reportId]);
  const shareText = useMemo(() => `Отчёт: ${reportName}`, [reportName]);
  const telegramUrl = useMemo(
    () => `https://t.me/share/url?url=${encodeURIComponent(reportUrl)}&text=${encodeURIComponent(shareText)}`,
    [reportUrl, shareText],
  );
  const vkUrl = useMemo(
    () => `https://vk.com/share.php?url=${encodeURIComponent(reportUrl)}&title=${encodeURIComponent(shareText)}`,
    [reportUrl, shareText],
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={triggerVariant}>
          <Share2 className="mr-2 h-4 w-4" />
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Поделиться отчётом</DialogTitle>
          <DialogDescription>
            Можно отправить ссылку наружу или сразу опубликовать отчёт в рабочей группе, чтобы коллеги увидели его в чате.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="rounded-2xl border border-border/80 bg-black/18 p-4 text-sm text-muted-foreground">
            {reportName}
            <div className="mt-2 break-all text-xs">{reportUrl}</div>
          </div>

          <div className="space-y-3 rounded-2xl border border-primary/18 bg-primary/8 p-4">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <Users2 className="h-4 w-4" />
              В рабочую группу
            </div>
            <div className="space-y-2">
              <Label>Группа</Label>
              <Select value={selectedGroupId} onValueChange={setSelectedGroupId}>
                <SelectTrigger>
                  <SelectValue placeholder="Выберите рабочую группу" />
                </SelectTrigger>
                <SelectContent>
                  {(groups.data ?? []).map((group) => (
                    <SelectItem key={group.id} value={group.id}>
                      {group.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Комментарий для чата</Label>
              <Textarea
                rows={3}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Коллеги, посмотрите, пожалуйста, этот отчёт по отменам и выручке."
              />
            </div>
            {shareToGroup.error ? (
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
                {shareToGroup.error.message}
              </div>
            ) : null}
            <Button className="w-full" onClick={() => shareToGroup.mutate()} disabled={!selectedGroupId || shareToGroup.isPending}>
              {shareToGroup.isPending ? "Публикуем…" : "Опубликовать в группе"}
            </Button>
          </div>

          <div className="space-y-3">
            <div className="text-sm font-medium text-foreground">Внешняя ссылка</div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Button asChild className="w-full">
                <a href={telegramUrl} target="_blank" rel="noreferrer">
                  <Send className="mr-2 h-4 w-4" />
                  Телеграм
                </a>
              </Button>
              <Button asChild variant="secondary" className="w-full">
                <a href={vkUrl} target="_blank" rel="noreferrer">
                  ВК
                </a>
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Ссылка на отчёт</Label>
            <Input value={reportUrl} readOnly />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
