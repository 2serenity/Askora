"use client";

import { useEffect } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { api } from "@/lib/api";

const profileSchema = z.object({
  full_name: z.string().min(3, "Минимум 3 символа"),
  timezone: z.string().min(2, "Укажите часовой пояс"),
  locale: z.string().min(2, "Укажите локаль"),
});

const passwordSchema = z
  .object({
    current_password: z.string().min(6, "Введите текущий пароль"),
    new_password: z.string().min(8, "Минимум 8 символов"),
    confirm_password: z.string().min(8, "Подтвердите новый пароль"),
  })
  .refine((value) => value.new_password === value.confirm_password, {
    path: ["confirm_password"],
    message: "Пароли не совпадают",
  });

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const auth = useAuth();

  const profileForm = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: "",
      timezone: "Europe/Kaliningrad",
      locale: "ru-RU",
    },
  });

  const passwordForm = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  useEffect(() => {
    if (auth.data?.user) {
      profileForm.reset({
        full_name: auth.data.user.full_name,
        timezone: auth.data.user.timezone,
        locale: auth.data.user.locale,
      });
    }
  }, [auth.data, profileForm]);

  const saveProfile = useMutation({
    mutationFn: (values: z.infer<typeof profileSchema>) => api.updateProfile(values),
    onSuccess: async (payload) => {
      await queryClient.setQueryData(["auth", "me"], payload);
    },
  });

  const changePassword = useMutation({
    mutationFn: (values: z.infer<typeof passwordSchema>) =>
      api.changePassword({
        current_password: values.current_password,
        new_password: values.new_password,
      }),
    onSuccess: async () => {
      passwordForm.reset();
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Профиль</h1>
        <p className="mt-2 text-muted-foreground">Здесь можно обновить имя, локаль, часовой пояс и пароль.</p>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Личные настройки</CardTitle>
            <CardDescription>Email используется как логин и здесь доступен только для чтения.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={profileForm.handleSubmit((values) => saveProfile.mutate(values))}>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input value={auth.data?.user.email ?? ""} readOnly />
              </div>
              <div className="space-y-2">
                <Label>Имя</Label>
                <Input {...profileForm.register("full_name")} />
                {profileForm.formState.errors.full_name ? <div className="text-sm text-rose-300">{profileForm.formState.errors.full_name.message}</div> : null}
              </div>
              <div className="space-y-2">
                <Label>Часовой пояс</Label>
                <Input {...profileForm.register("timezone")} />
                {profileForm.formState.errors.timezone ? <div className="text-sm text-rose-300">{profileForm.formState.errors.timezone.message}</div> : null}
              </div>
              <div className="space-y-2">
                <Label>Локаль интерфейса</Label>
                <Input {...profileForm.register("locale")} />
                {profileForm.formState.errors.locale ? <div className="text-sm text-rose-300">{profileForm.formState.errors.locale.message}</div> : null}
              </div>
              {saveProfile.error ? <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{saveProfile.error.message}</div> : null}
              <Button className="w-full" disabled={saveProfile.isPending}>
                {saveProfile.isPending ? "Сохраняем…" : "Сохранить настройки"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Смена пароля</CardTitle>
            <CardDescription>Пароль меняется сразу после проверки текущего значения.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={passwordForm.handleSubmit((values) => changePassword.mutate(values))}>
              <div className="space-y-2">
                <Label>Текущий пароль</Label>
                <Input type="password" {...passwordForm.register("current_password")} />
                {passwordForm.formState.errors.current_password ? <div className="text-sm text-rose-300">{passwordForm.formState.errors.current_password.message}</div> : null}
              </div>
              <div className="space-y-2">
                <Label>Новый пароль</Label>
                <Input type="password" {...passwordForm.register("new_password")} />
                {passwordForm.formState.errors.new_password ? <div className="text-sm text-rose-300">{passwordForm.formState.errors.new_password.message}</div> : null}
              </div>
              <div className="space-y-2">
                <Label>Повторите новый пароль</Label>
                <Input type="password" {...passwordForm.register("confirm_password")} />
                {passwordForm.formState.errors.confirm_password ? <div className="text-sm text-rose-300">{passwordForm.formState.errors.confirm_password.message}</div> : null}
              </div>
              {changePassword.error ? <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{changePassword.error.message}</div> : null}
              <Button className="w-full" disabled={changePassword.isPending}>
                {changePassword.isPending ? "Обновляем…" : "Обновить пароль"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
