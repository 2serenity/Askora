"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { getRoleLabel } from "@/lib/presentation";
import type { CreateUserRequest } from "@/types/api";

export function UserRoleTable({ canEditRoles }: { canEditRoles: boolean }) {
  const queryClient = useQueryClient();
  const [newUser, setNewUser] = useState<Pick<CreateUserRequest, "full_name" | "email" | "password" | "role">>({
    full_name: "",
    email: "",
    password: "",
    role: "business_user",
  });
  const { data } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: api.adminUsers
  });
  const mutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) => api.updateUserRole(userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] })
  });
  const statusMutation = useMutation({
    mutationFn: ({ userId, is_active }: { userId: string; is_active: boolean }) => api.updateUserStatus(userId, is_active),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
  const createMutation = useMutation({
    mutationFn: () =>
      api.createAdminUser({
        ...newUser,
        is_active: true,
      }),
    onSuccess: async () => {
      setNewUser({
        full_name: "",
        email: "",
        password: "",
        role: "business_user",
      });
      await queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Пользователи и роли</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {canEditRoles ? (
          <div className="grid gap-4 rounded-2xl border border-border/80 bg-black/24 p-4 lg:grid-cols-[1fr_1fr_0.8fr_0.8fr_auto]">
            <div className="space-y-2">
              <Label>ФИО</Label>
              <Input value={newUser.full_name} onChange={(event) => setNewUser((current) => ({ ...current, full_name: event.target.value }))} placeholder="Мария Сергеева" />
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={newUser.email} onChange={(event) => setNewUser((current) => ({ ...current, email: event.target.value }))} placeholder="maria@company.local" />
            </div>
            <div className="space-y-2">
              <Label>Пароль</Label>
              <Input type="password" value={newUser.password} onChange={(event) => setNewUser((current) => ({ ...current, password: event.target.value }))} placeholder="Минимум 8 символов" />
            </div>
            <div className="space-y-2">
              <Label>Роль</Label>
              <Select
                value={newUser.role}
                onValueChange={(value) =>
                  setNewUser((current) => ({
                    ...current,
                    role: value as CreateUserRequest["role"],
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Администратор</SelectItem>
                  <SelectItem value="analyst">Аналитик</SelectItem>
                  <SelectItem value="business_user">Пользователь</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                className="w-full"
                onClick={() => createMutation.mutate()}
                disabled={createMutation.isPending || !newUser.full_name || !newUser.email || !newUser.password}
              >
                {createMutation.isPending ? "Создаём…" : "Зарегистрировать"}
              </Button>
            </div>
          </div>
        ) : null}

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Пользователь</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Роль</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {(data ?? []).map((user) => (
              <TableRow key={user.id}>
                <TableCell>{user.full_name}</TableCell>
                <TableCell>{user.email}</TableCell>
                <TableCell>{getRoleLabel(user.role)}</TableCell>
                <TableCell>{user.is_active ? "Активен" : "Отключён"}</TableCell>
                <TableCell className="w-[220px]">
                  <div className="grid gap-2">
                    {canEditRoles ? (
                      <Select onValueChange={(value) => mutation.mutate({ userId: user.id, role: value })}>
                        <SelectTrigger>
                          <SelectValue placeholder="Изменить роль" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="admin">Администратор</SelectItem>
                          <SelectItem value="analyst">Аналитик</SelectItem>
                          <SelectItem value="business_user">Пользователь</SelectItem>
                        </SelectContent>
                      </Select>
                    ) : (
                      <Button variant="outline" disabled>
                        Только администратор
                      </Button>
                    )}
                    {canEditRoles ? (
                      <Button
                        variant={user.is_active ? "outline" : "secondary"}
                        onClick={() => statusMutation.mutate({ userId: user.id, is_active: !user.is_active })}
                      >
                        {user.is_active ? "Отключить" : "Включить"}
                      </Button>
                    ) : null}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
