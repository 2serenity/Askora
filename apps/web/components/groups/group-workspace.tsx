"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  Lock,
  MessageSquareText,
  Plus,
  Search,
  SendHorizontal,
  Trash2,
  UserPlus,
  Users2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ReportMessageCard } from "@/components/groups/report-message-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { getRoleLabel, getStatusLabel } from "@/lib/presentation";
import { cn } from "@/lib/utils";

type SidePanel = "members" | "reports" | null;

function initials(name: string) {
  return name
    .split(" ")
    .map((part) => part.trim()[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asString(value: unknown) {
  return typeof value === "string" ? value : "";
}

function asStringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.length > 0) : [];
}

function isReportMessage(payload: Record<string, unknown>) {
  const kind = asString(payload.kind);
  return kind === "report_share" || kind === "scheduled_report";
}

function getMessageDateLabel(value: string) {
  return new Date(value).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function GroupWorkspace() {
  const queryClient = useQueryClient();
  const feedRef = useRef<HTMLDivElement | null>(null);

  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [showGroupList, setShowGroupList] = useState(true);
  const [sidePanel, setSidePanel] = useState<SidePanel>(null);
  const [groupForm, setGroupForm] = useState({ name: "", description: "", is_private: true });
  const [message, setMessage] = useState("");
  const [memberUserId, setMemberUserId] = useState("");
  const [memberRole, setMemberRole] = useState("member");
  const [searchValue, setSearchValue] = useState("");
  const [feedFilter, setFeedFilter] = useState<"all" | "reports" | "messages">("all");

  const groups = useQuery({
    queryKey: ["groups"],
    queryFn: api.groups,
  });

  const availableUsers = useQuery({
    queryKey: ["groups", "users"],
    queryFn: api.groupUsers,
  });

  const groupDetail = useQuery({
    queryKey: ["groups", selectedGroupId],
    queryFn: () => api.group(selectedGroupId as string),
    enabled: Boolean(selectedGroupId),
    refetchInterval: 4000,
  });

  useEffect(() => {
    if (!selectedGroupId && groups.data?.length) {
      setSelectedGroupId(groups.data[0].id);
    }
  }, [groups.data, selectedGroupId]);

  useEffect(() => {
    if (!feedRef.current) {
      return;
    }
    feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [groupDetail.data?.messages.length, selectedGroupId]);

  const createGroup = useMutation({
    mutationFn: () =>
      api.createGroup({
        name: groupForm.name.trim(),
        description: groupForm.description.trim(),
        is_private: groupForm.is_private,
      }),
    onSuccess: async (created) => {
      setGroupForm({ name: "", description: "", is_private: true });
      setSelectedGroupId(created.id);
      setShowCreateGroup(false);
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
      await queryClient.invalidateQueries({ queryKey: ["groups", created.id] });
    },
  });

  const addMember = useMutation({
    mutationFn: () => api.saveGroupMember(selectedGroupId as string, { user_id: memberUserId, role: memberRole }),
    onSuccess: async () => {
      setMemberUserId("");
      setMemberRole("member");
      await queryClient.invalidateQueries({ queryKey: ["groups", selectedGroupId] });
    },
  });

  const removeMember = useMutation({
    mutationFn: (userId: string) => api.deleteGroupMember(selectedGroupId as string, userId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["groups", selectedGroupId] });
    },
  });

  const postMessage = useMutation({
    mutationFn: () => api.postGroupMessage(selectedGroupId as string, { body: message.trim() }),
    onSuccess: async () => {
      setMessage("");
      await queryClient.invalidateQueries({ queryKey: ["groups", selectedGroupId] });
    },
  });

  const deleteGroup = useMutation({
    mutationFn: () => api.deleteGroup(selectedGroupId as string),
    onSuccess: async () => {
      const nextId = groups.data?.find((item) => item.id !== selectedGroupId)?.id ?? null;
      setSelectedGroupId(nextId);
      setSidePanel(null);
      await queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  const currentRole = groupDetail.data?.current_user_role ?? null;
  const canManage = currentRole === "admin" || currentRole === "owner" || currentRole === "manager";
  const canPost = currentRole !== "viewer";
  const normalizedSearch = searchValue.trim().toLowerCase();

  const filteredMessages = useMemo(() => {
    const items = groupDetail.data?.messages ?? [];
    return items.filter((item) => {
      const payload = asRecord(item.payload_json);
      const matchesFilter =
        feedFilter === "all" ||
        (feedFilter === "reports" && isReportMessage(payload)) ||
        (feedFilter === "messages" && !isReportMessage(payload));

      if (!matchesFilter) {
        return false;
      }

      if (!normalizedSearch) {
        return true;
      }

      return [item.author_name, item.body, asString(payload.report_name), asString(payload.question), ...asStringArray(payload.metric_labels)]
        .join(" ")
        .toLowerCase()
        .includes(normalizedSearch);
    });
  }, [feedFilter, groupDetail.data?.messages, normalizedSearch]);

  const visibleSharedReports = useMemo(() => {
    const items = groupDetail.data?.shared_reports ?? [];
    if (!normalizedSearch) {
      return items;
    }
    return items.filter((item) =>
      [item.report_name, item.report_description ?? "", item.report_question, item.owner_name, ...(item.metric_labels ?? [])]
        .join(" ")
        .toLowerCase()
        .includes(normalizedSearch),
    );
  }, [groupDetail.data?.shared_reports, normalizedSearch]);

  const availableToAdd = useMemo(() => {
    const existing = new Set((groupDetail.data?.members ?? []).map((item) => item.user_id));
    return (availableUsers.data ?? []).filter((item) => !existing.has(item.id));
  }, [availableUsers.data, groupDetail.data?.members]);

  const reportMessageCount = useMemo(
    () => (groupDetail.data?.messages ?? []).filter((item) => isReportMessage(asRecord(item.payload_json))).length,
    [groupDetail.data?.messages],
  );

  return (
    <div className="grid min-h-[calc(100vh-8rem)] gap-4 xl:grid-cols-[270px_minmax(0,1fr)] 2xl:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="space-y-3 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:self-start xl:overflow-y-auto">
        <div className="rounded-[24px] border border-border/80 bg-black/22 p-3">
          <button
            type="button"
            onClick={() => setShowCreateGroup((current) => !current)}
            className="flex w-full items-center justify-between rounded-[20px] border border-border/70 bg-black/24 px-3 py-2.5 text-left transition hover:border-primary/18 hover:bg-primary/6"
          >
            <span className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Plus className="h-4 w-4 text-primary" />
              Новая группа
            </span>
            <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition", showCreateGroup ? "rotate-180" : "")} />
          </button>

          {showCreateGroup ? (
            <div className="mt-3 space-y-3 rounded-[20px] border border-border/80 bg-black/24 p-3">
              <div className="space-y-2">
                <Label>Название</Label>
                <Input
                  value={groupForm.name}
                  onChange={(event) => setGroupForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="Финансы и продажи"
                />
              </div>
              <div className="space-y-2">
                <Label>Описание</Label>
                <Textarea
                  rows={3}
                  value={groupForm.description}
                  onChange={(event) => setGroupForm((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Отчёты по заказам, отменам и выручке"
                />
              </div>
              <div className="space-y-2">
                <Label>Тип доступа</Label>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={groupForm.is_private ? "default" : "outline"}
                    onClick={() => setGroupForm((current) => ({ ...current, is_private: true }))}
                  >
                    Закрытая
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={!groupForm.is_private ? "default" : "outline"}
                    onClick={() => setGroupForm((current) => ({ ...current, is_private: false }))}
                  >
                    Открытая
                  </Button>
                </div>
              </div>
              <Button className="w-full" onClick={() => createGroup.mutate()} disabled={createGroup.isPending || !groupForm.name.trim()}>
                {createGroup.isPending ? "Создаём..." : "Создать"}
              </Button>
            </div>
          ) : null}
        </div>

        <div className="rounded-[24px] border border-border/80 bg-black/22 p-3">
          <button
            type="button"
            onClick={() => setShowGroupList((current) => !current)}
            className="flex w-full items-center justify-between rounded-[20px] border border-border/70 bg-black/24 px-3 py-2.5 text-left transition hover:border-primary/18 hover:bg-primary/6"
          >
            <span className="flex items-center gap-2 text-sm font-medium text-foreground">
              <MessageSquareText className="h-4 w-4 text-primary" />
              Чаты
              <Badge variant="outline">{groups.data?.length ?? 0}</Badge>
            </span>
            <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition", showGroupList ? "rotate-180" : "")} />
          </button>

          {showGroupList ? (
            <div className="mt-3 space-y-2">
              {(groups.data ?? []).map((group) => (
                <button
                  key={group.id}
                  onClick={() => setSelectedGroupId(group.id)}
                  className={cn(
                    "w-full rounded-[22px] border p-3.5 text-left transition",
                    selectedGroupId === group.id
                      ? "border-primary/30 bg-primary/10 shadow-[0_0_24px_rgba(122,255,76,0.08)]"
                      : "border-border/80 bg-black/24 hover:border-primary/18 hover:bg-primary/6",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2 font-medium text-foreground">
                        <span className="truncate">{group.name}</span>
                        {group.is_private ? <Lock className="h-3.5 w-3.5 text-muted-foreground" /> : null}
                      </div>
                      <div className="line-clamp-2 text-sm text-muted-foreground">{group.description || "Без описания"}</div>
                    </div>
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-primary/16 bg-primary/8 text-xs font-semibold text-primary">
                      {group.member_count}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </aside>

      <section className="min-w-0">
        {!groupDetail.data ? (
          <Card>
            <CardContent className="pt-6 text-muted-foreground">
              Выберите группу слева или создайте новую, чтобы открыть рабочий чат.
            </CardContent>
          </Card>
        ) : (
          <Card className="relative flex h-[calc(100vh-7.5rem)] min-h-[720px] flex-col overflow-hidden">
            <CardHeader className="border-b border-border/80 bg-black/18 px-4 py-4 md:px-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <CardTitle>{groupDetail.data.name}</CardTitle>
                    <Badge variant="outline">{groupDetail.data.is_private ? "Закрытая" : "Открытая"}</Badge>
                    {currentRole ? <Badge variant="secondary">{getRoleLabel(currentRole)}</Badge> : null}
                  </div>
                  <CardDescription>{groupDetail.data.description || "Описание группы не заполнено."}</CardDescription>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge variant="outline">{groupDetail.data.member_count} участников</Badge>
                  <Badge variant="outline">{reportMessageCount} отчётов в чате</Badge>
                  <Button
                    variant={sidePanel === "members" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSidePanel((current) => (current === "members" ? null : "members"))}
                  >
                    <Users2 className="mr-2 h-4 w-4" />
                    Участники
                  </Button>
                  <Button
                    variant={sidePanel === "reports" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSidePanel((current) => (current === "reports" ? null : "reports"))}
                  >
                    <MessageSquareText className="mr-2 h-4 w-4" />
                    Отчёты
                  </Button>
                  {canManage ? (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        if (window.confirm("Удалить группу вместе с чатом и общей историей?")) {
                          deleteGroup.mutate();
                        }
                      }}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Удалить
                    </Button>
                  ) : null}
                </div>
              </div>
            </CardHeader>

            <div className="border-b border-border/80 bg-black/12 px-4 py-3 md:px-5">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="relative w-full xl:max-w-lg">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    value={searchValue}
                    onChange={(event) => setSearchValue(event.target.value)}
                    placeholder="Поиск по сообщениям, отчётам и метрикам"
                  />
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button variant={feedFilter === "all" ? "default" : "outline"} size="sm" onClick={() => setFeedFilter("all")}>
                    Всё
                  </Button>
                  <Button variant={feedFilter === "reports" ? "default" : "outline"} size="sm" onClick={() => setFeedFilter("reports")}>
                    Отчёты
                  </Button>
                  <Button variant={feedFilter === "messages" ? "default" : "outline"} size="sm" onClick={() => setFeedFilter("messages")}>
                    Сообщения
                  </Button>
                </div>
              </div>
            </div>

            <div className="relative min-h-0 flex-1">
              <div className={cn("flex h-full min-h-0 flex-col", sidePanel ? "xl:pr-[400px]" : "")}>
                <div
                  ref={feedRef}
                  className="min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top,_rgba(122,255,76,0.05),_transparent_40%),linear-gradient(180deg,rgba(8,10,8,0.88),rgba(5,7,5,0.94))] px-4 py-5 md:px-5"
                >
                  <div className="mx-auto flex w-full max-w-[min(100%,88rem)] flex-col gap-4">
                    {filteredMessages.length ? (
                      filteredMessages.map((item) => {
                        const payload = asRecord(item.payload_json);
                        const reportKind = asString(payload.kind);
                        const reportMessage = isReportMessage(payload);

                        return (
                          <div key={item.id} className="flex items-start gap-3">
                            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-primary/18 bg-primary/10 text-sm font-semibold text-primary">
                              {initials(item.author_name)}
                            </div>

                            <div className="min-w-0 flex-1 space-y-2">
                              <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                                <span>{item.author_name}</span>
                                <span>•</span>
                                <span>{getMessageDateLabel(item.created_at)}</span>
                              </div>

                              {reportMessage ? (
                                <div className="max-w-[min(100%,72rem)]">
                                  <ReportMessageCard
                                    title={asString(payload.report_name) || "Отчёт"}
                                    question={asString(payload.question)}
                                    reportId={asString(payload.report_id) || undefined}
                                    chartType={asString(payload.chart_type) || undefined}
                                    metricLabels={asStringArray(payload.metric_labels)}
                                    periodLabel={asString(payload.period_label) || undefined}
                                    preview={payload.preview}
                                    queryPlan={asRecord(payload.query_plan_json)}
                                    note={item.body}
                                    kindLabel={reportKind === "scheduled_report" ? "Отчёт по расписанию" : "Поделились отчётом"}
                                  />
                                </div>
                              ) : (
                                <div className="max-w-[min(100%,58rem)] rounded-[26px] border border-border/80 bg-black/32 px-4 py-3 text-sm leading-6 text-foreground shadow-[0_12px_36px_rgba(0,0,0,0.22)]">
                                  {item.body}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <div className="rounded-[28px] border border-dashed border-border/80 bg-black/24 p-6 text-sm text-muted-foreground">
                        По текущим фильтрам сообщений нет. Попробуйте другой поиск или опубликуйте отчёт в чат.
                      </div>
                    )}
                  </div>
                </div>

                <div className="border-t border-border/80 bg-black/18 px-4 py-4 md:px-5">
                  {canPost ? (
                    <div className="mx-auto w-full max-w-[min(100%,88rem)] space-y-3">
                      <Textarea
                        rows={3}
                        className="max-h-32 min-h-[92px] resize-none"
                        value={message}
                        onChange={(event) => setMessage(event.target.value)}
                        onKeyDown={(event) => {
                          if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && message.trim() && !postMessage.isPending) {
                            event.preventDefault();
                            postMessage.mutate();
                          }
                        }}
                        placeholder="Напишите сообщение коллегам. Для быстрой отправки можно нажать Ctrl+Enter."
                      />
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-xs text-muted-foreground">
                          Общие отчёты автоматически появляются в ленте с графиком и краткими данными.
                        </div>
                        <Button onClick={() => postMessage.mutate()} disabled={!message.trim() || postMessage.isPending}>
                          <SendHorizontal className="mr-2 h-4 w-4" />
                          {postMessage.isPending ? "Отправляем..." : "Отправить"}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="mx-auto w-full max-w-[min(100%,88rem)] rounded-2xl border border-border/80 bg-black/22 px-4 py-3 text-sm text-muted-foreground">
                      У вас режим просмотра. Отправка сообщений и публикация отчётов недоступны.
                    </div>
                  )}
                </div>
              </div>

              {sidePanel ? (
                <aside className="absolute inset-y-0 right-0 z-10 w-full max-w-[400px] border-l border-border/80 bg-[#090c09]/96 backdrop-blur-xl">
                  <div className="flex h-full flex-col">
                    <div className="flex items-center justify-between border-b border-border/80 px-4 py-4">
                      <div className="space-y-1">
                        <div className="text-sm font-semibold text-foreground">
                          {sidePanel === "members" ? "Участники группы" : "Последние общие отчёты"}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {sidePanel === "members"
                            ? "Управление доступом к чату и публикациям внутри группы."
                            : "Отчёты, которыми уже поделились в этом чате."}
                        </div>
                      </div>
                      <Button variant="ghost" size="sm" onClick={() => setSidePanel(null)}>
                        <X className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="min-h-0 flex-1 overflow-y-auto p-4">
                      {sidePanel === "members" ? (
                        <div className="space-y-4">
                          {canManage ? (
                            <div className="space-y-3 rounded-[24px] border border-border/80 bg-black/24 p-4">
                              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                                <UserPlus className="h-4 w-4" />
                                Добавить участника
                              </div>
                              <Select value={memberUserId} onValueChange={setMemberUserId}>
                                <SelectTrigger>
                                  <SelectValue placeholder="Выберите сотрудника" />
                                </SelectTrigger>
                                <SelectContent>
                                  {availableToAdd.map((item) => (
                                    <SelectItem key={item.id} value={item.id}>
                                      {item.full_name} • {item.email}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <Select value={memberRole} onValueChange={setMemberRole}>
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="manager">Менеджер группы</SelectItem>
                                  <SelectItem value="member">Участник</SelectItem>
                                  <SelectItem value="viewer">Только просмотр</SelectItem>
                                </SelectContent>
                              </Select>
                              <Button onClick={() => addMember.mutate()} disabled={!memberUserId || addMember.isPending}>
                                {addMember.isPending ? "Сохраняем..." : "Добавить"}
                              </Button>
                            </div>
                          ) : null}

                          <div className="space-y-2">
                            {groupDetail.data.members.map((member) => (
                              <div key={member.id} className="flex items-center justify-between gap-3 rounded-[22px] border border-border/80 bg-black/24 px-3 py-3">
                                <div className="flex min-w-0 items-center gap-3">
                                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-primary/16 bg-primary/8 text-sm font-semibold text-primary">
                                    {initials(member.full_name)}
                                  </div>
                                  <div className="min-w-0">
                                    <div className="truncate text-sm font-medium text-foreground">{member.full_name}</div>
                                    <div className="truncate text-xs text-muted-foreground">{member.email}</div>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Badge variant="outline">{getRoleLabel(member.role)}</Badge>
                                  {canManage && member.role !== "owner" ? (
                                    <Button variant="ghost" size="sm" onClick={() => removeMember.mutate(member.user_id)}>
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  ) : null}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {visibleSharedReports.length ? (
                            visibleSharedReports.map((item) => (
                              <div key={item.id} className="space-y-2">
                                <ReportMessageCard
                                  compact
                                  title={item.report_name}
                                  question={item.report_question}
                                  reportId={item.report_id}
                                  chartType={item.chart_type}
                                  metricLabels={item.metric_labels}
                                  periodLabel={item.period_label}
                                  preview={item.preview_json}
                                  queryPlan={item.query_plan_json}
                                  kindLabel="Общий отчёт"
                                />
                                <div className="flex flex-wrap gap-2 px-1 text-xs text-muted-foreground">
                                  <span>Автор: {item.owner_name}</span>
                                  {item.last_run_status ? <span>• Последний запуск: {getStatusLabel(item.last_run_status)}</span> : null}
                                  {item.last_run_at ? <span>• {getMessageDateLabel(item.last_run_at)}</span> : null}
                                </div>
                              </div>
                            ))
                          ) : (
                            <div className="rounded-[24px] border border-dashed border-border/80 bg-black/24 p-4 text-sm text-muted-foreground">
                              Пока нет общих отчётов. Сохраните отчёт и отправьте его в группу из workspace.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </aside>
              ) : null}
            </div>
          </Card>
        )}
      </section>
    </div>
  );
}
