"use client";

import { AuditLogList } from "@/components/admin/audit-log-list";
import { DataSourceManager } from "@/components/admin/data-source-manager";
import { RequestTraceList } from "@/components/admin/request-trace-list";
import { SemanticEditor } from "@/components/admin/semantic-editor";
import { TemplateManager } from "@/components/admin/template-manager";
import { UserRoleTable } from "@/components/admin/user-role-table";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/hooks/use-auth";

export default function AdminPage() {
  const { data, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">Проверяем права доступа…</CardContent>
      </Card>
    );
  }

  if (!data || !["admin", "analyst"].includes(data.user.role)) {
    return (
      <Card>
        <CardContent className="pt-6">
          Эта страница доступна аналитикам и администраторам. Для обычного пользователя основной точкой входа остаётся рабочая область.
        </CardContent>
      </Card>
    );
  }

  const isAdmin = data.user.role === "admin";
  const defaultTab = isAdmin ? "users" : "semantic";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Администрирование</h1>
        <p className="mt-2 text-muted-foreground">
          Управление ролями, источниками данных, семантическим слоем, шаблонами и прозрачностью работы AI-пайплайна.
        </p>
      </div>

      <Tabs defaultValue={defaultTab} className="space-y-4">
        <TabsList className="w-full justify-start overflow-x-auto">
          {isAdmin ? <TabsTrigger value="users">Пользователи</TabsTrigger> : null}
          {isAdmin ? <TabsTrigger value="sources">Источники</TabsTrigger> : null}
          <TabsTrigger value="semantic">Семантика</TabsTrigger>
          <TabsTrigger value="templates">Шаблоны</TabsTrigger>
          {isAdmin ? <TabsTrigger value="audit">Аудит</TabsTrigger> : null}
          {isAdmin ? <TabsTrigger value="trace">AI trace</TabsTrigger> : null}
        </TabsList>

        {isAdmin ? (
          <TabsContent value="users" className="mt-0">
            <UserRoleTable canEditRoles />
          </TabsContent>
        ) : null}

        {isAdmin ? (
          <TabsContent value="sources" className="mt-0">
            <DataSourceManager />
          </TabsContent>
        ) : null}

        <TabsContent value="semantic" className="mt-0">
          <SemanticEditor />
        </TabsContent>

        <TabsContent value="templates" className="mt-0">
          <TemplateManager />
        </TabsContent>

        {isAdmin ? (
          <TabsContent value="audit" className="mt-0">
            <AuditLogList />
          </TabsContent>
        ) : null}

        {isAdmin ? (
          <TabsContent value="trace" className="mt-0">
            <RequestTraceList />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  );
}
