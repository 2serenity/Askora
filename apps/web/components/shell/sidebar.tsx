"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BarChart3, FileClock, Files, LogOut, Settings2, Shield, Sparkles, Users2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import type { UserSummary } from "@/types/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { getRoleLabel } from "@/lib/presentation";

const baseItems = [
  { href: "/workspace", label: "Аналитика", icon: Sparkles },
  { href: "/history", label: "История", icon: FileClock },
  { href: "/reports", label: "Отчёты", icon: Files },
  { href: "/groups", label: "Группы", icon: Users2 },
  { href: "/profile", label: "Профиль", icon: Settings2 },
];

export function Sidebar({ user }: { user: UserSummary }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const isAdminView = pathname === "/admin";
  const mutation = useMutation({
    mutationFn: api.logout,
    onSuccess: async () => {
      queryClient.clear();
      router.push("/login");
    },
  });

  const items = [...baseItems];
  if (["admin", "analyst"].includes(user.role)) {
    items.push({ href: "/admin", label: "Админка", icon: Shield });
  }

  return (
    <aside
      className={cn(
        "rounded-[28px] bg-black/55 p-5 text-white shadow-[0_24px_80px_rgba(0,0,0,0.45)] backdrop-blur",
        isAdminView ? "border border-border/80" : "border border-primary/12",
      )}
    >
      <div className="space-y-4">
        <div className="space-y-4">
          <Link href="/workspace" className="group flex items-center gap-4">
            <span className="relative h-12 w-12 overflow-hidden rounded-full bg-transparent">
              <Image
                src="/askora-logo.svg"
                alt="Askora"
                fill
                className="object-contain drop-shadow-[0_0_14px_rgba(49,255,47,0.22)] transition group-hover:drop-shadow-[0_0_20px_rgba(49,255,47,0.28)]"
                priority
              />
            </span>
            <div className="leading-tight">
              <div className="text-[30px] font-semibold tracking-tight">Askora</div>
              <div className="mt-1 text-xs font-semibold uppercase tracking-[0.22em] text-primary">AI-АССИСТЕНТ ЗАПРОСОВ</div>
            </div>
          </Link>
          <p className="text-sm leading-relaxed text-white/60">
            Безопасный SQL, отчёты,
            <br />
            расписания и рабочие группы в
            <br />
            одном рабочем контуре.
          </p>
        </div>
      </div>

      <nav className="mt-8 space-y-2">
        {items.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-2xl px-4 py-3 text-sm transition-colors",
                active
                  ? isAdminView
                    ? "bg-white text-black"
                    : "bg-primary text-primary-foreground"
                  : isAdminView
                    ? "text-white/70 hover:bg-white/10 hover:text-white"
                    : "text-white/70 hover:bg-primary/10 hover:text-white",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-8 rounded-2xl border border-border/80 bg-white/5 p-4">
        <div className="text-sm font-medium">{user.full_name}</div>
        <div className="mt-1 text-xs text-white/60">{user.email}</div>
        <div className="mt-3 inline-flex rounded-full bg-primary/12 px-3 py-1 text-xs text-primary">{getRoleLabel(user.role)}</div>
        <div className="mt-3 text-xs text-white/50">Часовой пояс: {user.timezone}</div>
      </div>

      <Button variant="outline" className="mt-4 w-full border-primary/20 bg-transparent text-white hover:bg-primary/10" onClick={() => mutation.mutate()}>
        <LogOut className="mr-2 h-4 w-4" />
        Выйти
      </Button>
    </aside>
  );
}
