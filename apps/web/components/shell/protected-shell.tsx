"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";

import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

import { Sidebar } from "./sidebar";

export function ProtectedShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data, isLoading, isError } = useAuth();
  const isAdminView = pathname === "/admin";

  useEffect(() => {
    if (!isLoading && (isError || !data)) {
      router.push("/login");
    }
  }, [data, isError, isLoading, router]);

  if (isLoading || !data) {
    return (
      <main className="page-shell min-h-screen px-6 py-10">
        <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-7xl items-center justify-center rounded-3xl border border-primary/12 bg-black/45 text-muted-foreground">
          Проверяем сессию...
        </div>
      </main>
    );
  }

  return (
    <main
      className={cn(
        "page-shell min-h-screen px-4 py-4 md:px-6 md:py-6",
        isAdminView && "page-shell--neutral bg-[#050605]",
      )}
    >
      <div className="mx-auto grid max-w-[1600px] gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Sidebar user={data.user} />
        <div
          className={cn(
            "min-w-0 rounded-[28px] p-4 shadow-[0_24px_80px_rgba(0,0,0,0.4)] backdrop-blur md:p-6",
            isAdminView ? "border border-border/80 bg-[#0b0d0b]" : "border border-primary/10 bg-black/38",
          )}
        >
          {children}
        </div>
      </div>
    </main>
  );
}
