import type { ReactNode } from "react";

import { ProtectedShell } from "@/components/shell/protected-shell";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return <ProtectedShell>{children}</ProtectedShell>;
}
